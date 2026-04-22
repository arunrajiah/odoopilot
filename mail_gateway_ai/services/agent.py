import json
import logging
from datetime import date

from odoo import fields

from .llm import LLMClient
from .tools import TOOL_DEFINITIONS, WRITE_TOOLS, execute_tool

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are OdooPilot, an AI assistant integrated with Odoo ERP.
You help users query and manage their Odoo data via Telegram.
Today is {today}. The user's name is {user_name}.

Rules:
- Be concise. Use bullet points for lists.
- For write/mutating operations (mark done, confirm order, etc.), always ask for confirmation first using the tool - never execute them directly.
- If a module isn't installed, say so politely.
- Respond in the same language the user writes in.
"""


class OdooPilotAgent:
    def __init__(self, env, tg):
        self.env = env  # Odoo env scoped to the linked user
        self.tg = tg
        cfg = env["ir.config_parameter"].sudo()
        provider = cfg.get_param("mail_gateway_ai.llm_provider") or "anthropic"
        api_key = cfg.get_param("mail_gateway_ai.llm_api_key") or ""
        model = cfg.get_param("mail_gateway_ai.llm_model") or ""
        self.llm = LLMClient(provider, api_key, model)

    def handle_message(self, chat_id: str, text: str) -> None:
        session = self.env["mail.gateway.ai.session"].sudo().get_or_create("telegram", chat_id)

        system = SYSTEM_PROMPT.format(
            today=date.today().strftime("%A, %d %B %Y"),
            user_name=self.env.user.name,
        )
        messages = [{"role": "system", "content": system}] + session.get_messages()
        messages.append({"role": "user", "content": text})

        try:
            response_text = self._run_loop(chat_id, messages, session)
        except Exception as e:
            _logger.exception("Agent error for chat %s", chat_id)
            response_text = "Sorry, I encountered an error. Please try again."

        if response_text:
            self.tg.send_message(chat_id, response_text)
            session.append_message("user", text)
            session.append_message("assistant", response_text)

        # Write audit log
        self._audit(chat_id, text, response_text)

    def _run_loop(self, chat_id: str, messages: list, session, max_iterations: int = 5) -> str:
        """LLM tool-use loop. Returns final text response."""
        for _ in range(max_iterations):
            result = self.llm.chat(messages, TOOL_DEFINITIONS)

            if result["stop_reason"] in ("end_turn", "stop") or not result["tool_calls"]:
                return result["text"]

            # Process tool calls
            tool_calls = result["tool_calls"]
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["name"]
                args = tc["args"]

                if tool_name in WRITE_TOOLS:
                    # Save pending action and ask for confirmation
                    session.sudo().write({
                        "pending_tool": tool_name,
                        "pending_args": json.dumps(args),
                    })
                    question = f"<b>Confirm action</b>\n\nTool: <code>{tool_name}</code>\nArgs: <code>{json.dumps(args)}</code>\n\nProceed?"
                    self.tg.send_confirmation(chat_id, question)
                    return ""  # Wait for user confirmation

                result_str = execute_tool(self.env, tool_name, args)
                tool_results.append(result_str)

            # Append tool results to message history for next LLM call
            extra = self.llm.build_tool_result_messages(tool_calls, tool_results)
            messages.extend(extra)

        return "I wasn't able to complete your request after several attempts."

    def execute_confirmed(self, chat_id: str, tool_name: str, args: dict) -> None:
        """Execute a write tool after user confirmed."""
        result = execute_tool(self.env, tool_name, args)
        self.tg.send_message(chat_id, result)
        self._audit(chat_id, f"[confirmed] {tool_name}", result)

    def _audit(self, chat_id: str, user_text: str, response: str) -> None:
        try:
            self.env["mail.gateway.ai.audit"].sudo().create({
                "timestamp": fields.Datetime.now(),
                "user_id": self.env.uid,
                "channel": "telegram",
                "tool_name": "chat",
                "tool_args": user_text[:500],
                "result_summary": (response or "")[:500],
                "success": True,
            })
        except Exception:
            pass  # Audit failure must never break the main flow
