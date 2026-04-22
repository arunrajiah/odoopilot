import json
import logging
from datetime import date

from odoo import fields

from .llm import LLMClient
from .tools import TOOL_DEFINITIONS, WRITE_TOOLS, _fmt_confirmation, execute_tool

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are OdooPilot, an AI assistant integrated with Odoo ERP.
You help users query and manage their Odoo data via Telegram.
Today is {today}. The user's name is {user_name}.

Rules:
- Be concise. Use bullet points for lists.
- For write/mutating operations, always request confirmation first — never execute them directly.
- If a module isn't installed (e.g. CRM, Purchase), say so politely.
- Respond in the same language the user writes in.
"""


class OdooPilotAgent:
    def __init__(self, env, tg):
        self.env = env  # Odoo env scoped to the linked user
        self.tg = tg
        cfg = env["ir.config_parameter"].sudo()
        provider = cfg.get_param("odoopilot.llm_provider") or "anthropic"
        api_key = cfg.get_param("odoopilot.llm_api_key") or ""
        model = cfg.get_param("odoopilot.llm_model") or ""
        self.llm = LLMClient(provider, api_key, model)

    def handle_message(self, chat_id: str, text: str) -> None:
        session = (
            self.env["odoopilot.session"].sudo().get_or_create("telegram", chat_id)
        )

        system = SYSTEM_PROMPT.format(
            today=date.today().strftime("%A, %d %B %Y"),
            user_name=self.env.user.name,
        )
        messages = [{"role": "system", "content": system}] + session.get_messages()
        messages.append({"role": "user", "content": text})

        try:
            response_text = self._run_loop(chat_id, messages, session)
        except Exception:
            _logger.exception("Agent error for chat %s", chat_id)
            response_text = "Sorry, I encountered an error. Please try again."

        if response_text:
            self.tg.send_message(chat_id, response_text)
            session.append_message("user", text)
            session.append_message("assistant", response_text)

        self._audit(chat_id, "chat", {"text": text}, response_text or "", True)

    def _run_loop(
        self, chat_id: str, messages: list, session, max_iterations: int = 5
    ) -> str:
        """LLM tool-use loop. Returns final text response."""
        for _ in range(max_iterations):
            result = self.llm.chat(messages, TOOL_DEFINITIONS)

            if (
                result["stop_reason"] in ("end_turn", "stop")
                or not result["tool_calls"]
            ):
                return result["text"]

            tool_calls = result["tool_calls"]
            tool_results = []

            for tc in tool_calls:
                tool_name = tc["name"]
                args = tc["args"]

                if tool_name in WRITE_TOOLS:
                    # Store the pending action and ask for confirmation
                    session.sudo().write(
                        {
                            "pending_tool": tool_name,
                            "pending_args": json.dumps(args),
                        }
                    )
                    question = _fmt_confirmation(tool_name, args)
                    self.tg.send_confirmation(chat_id, question)
                    return ""  # Pause — wait for user's Yes/No

                result_str = execute_tool(self.env, tool_name, args)
                self._audit(chat_id, tool_name, args, result_str, True)
                tool_results.append(result_str)

            extra = self.llm.build_tool_result_messages(tool_calls, tool_results)
            messages.extend(extra)

        return "I wasn't able to complete your request after several attempts."

    def execute_confirmed(self, chat_id: str, tool_name: str, args: dict) -> None:
        """Execute a write tool after the user confirmed via inline keyboard."""
        try:
            result = execute_tool(self.env, tool_name, args)
            success = True
        except Exception as e:
            result = f"Error: {e}"
            success = False
            _logger.exception(
                "Confirmed tool %s failed for chat %s", tool_name, chat_id
            )

        self.tg.send_message(chat_id, result)
        self._audit(chat_id, tool_name, args, result, success)

    def _audit(
        self,
        chat_id: str,
        tool_name: str,
        tool_args: dict,
        result: str,
        success: bool,
    ) -> None:
        try:
            self.env["odoopilot.audit"].sudo().create(
                {
                    "timestamp": fields.Datetime.now(),
                    "user_id": self.env.uid,
                    "channel": "telegram",
                    "tool_name": tool_name,
                    "tool_args": json.dumps(tool_args)[:500],
                    "result_summary": result[:500],
                    "success": success,
                }
            )
        except Exception:
            pass  # Audit failure must never break the main flow
