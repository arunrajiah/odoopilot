import json
import logging
from datetime import date

from odoo import fields

from .llm import LLMClient
from .tools import (
    TOOL_DEFINITIONS,
    WRITE_TOOLS,
    execute_tool,
    preflight_write,
)

_logger = logging.getLogger(__name__)

# ISO 639-1 code → English name used in the system prompt
_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "tr": "Turkish",
    "pl": "Polish",
    "hi": "Hindi",
}

SYSTEM_PROMPT = """You are OdooPilot, an AI assistant integrated with Odoo ERP.
You help users query and manage their Odoo data via Telegram and WhatsApp.
Today is {today}. The user's name is {user_name}.

Rules:
- Be concise. Use bullet points for lists.
- For write/mutating operations, always request confirmation first — never execute them directly.
- If a module isn't installed (e.g. CRM, Purchase), say so politely.
- {language_instruction}
"""


def _language_instruction(language: str) -> str:
    """Return the language rule for the system prompt."""
    if language and language in _LANGUAGE_NAMES:
        return f"Always respond in {_LANGUAGE_NAMES[language]}."
    return "Respond in the same language the user writes in."


class OdooPilotAgent:
    def __init__(self, env, client, channel: str = "telegram"):
        self.env = env  # Odoo env scoped to the linked user
        self.tg = client  # messaging client (Telegram or WhatsApp)
        self.channel = channel
        cfg = env["ir.config_parameter"].sudo()
        provider = cfg.get_param("odoopilot.llm_provider") or "anthropic"
        api_key = cfg.get_param("odoopilot.llm_api_key") or ""
        model = cfg.get_param("odoopilot.llm_model") or ""
        self.llm = LLMClient(provider, api_key, model)

    def _get_language(self, chat_id: str) -> str:
        """Return the language code stored in the user's identity, or '' for auto."""
        identity = (
            self.env["odoopilot.identity"]
            .sudo()
            .search(
                [
                    ("channel", "=", self.channel),
                    ("chat_id", "=", chat_id),
                ],
                limit=1,
            )
        )
        return identity.language if identity else ""

    def handle_message(self, chat_id: str, text: str) -> None:
        session = (
            self.env["odoopilot.session"].sudo().get_or_create(self.channel, chat_id)
        )

        language = self._get_language(chat_id)
        system = SYSTEM_PROMPT.format(
            today=date.today().strftime("%A, %d %B %Y"),
            user_name=self.env.user.name,
            language_instruction=_language_instruction(language),
        )
        messages = [{"role": "system", "content": system}] + session.get_messages()
        messages.append({"role": "user", "content": text})

        try:
            response_text = self._run_loop(chat_id, messages, session)
        except Exception:
            _logger.exception("Agent error for chat %s", chat_id)
            response_text = "Sorry, I encountered an error. Please try again."

        session.append_message("user", text)
        if response_text:
            self.tg.send_message(chat_id, response_text)
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

            # Separate read and write tools; only handle the first write tool per turn
            read_calls = []
            write_call = None
            for tc in tool_calls:
                if tc["name"] in WRITE_TOOLS:
                    if write_call is None:
                        write_call = tc
                else:
                    read_calls.append(tc)

            # Execute all read tools
            read_results = []
            for tc in read_calls:
                result_str = execute_tool(self.env, tc["name"], tc["args"])
                self._audit(chat_id, tc["name"], tc["args"], result_str, True)
                read_results.append(result_str)

            if read_results:
                extra = self.llm.build_tool_result_messages(read_calls, read_results)
                messages.extend(extra)

            if write_call:
                # Resolve the write target BEFORE staging. The resolved record
                # id is what gets stored in pending_args, and the confirmation
                # prompt shows the resolved record's display_name (not the
                # LLM's argument string). This prevents a prompt-injection
                # attack where a poisoned record lures the LLM into supplying
                # a wildcard-y name that the executor would expand to a
                # different record than the user thinks they're confirming.
                preflight = preflight_write(
                    self.env, write_call["name"], write_call["args"]
                )
                if not preflight["ok"]:
                    err_msg = preflight["error"]
                    self.tg.send_message(chat_id, err_msg)
                    self._audit(
                        chat_id, write_call["name"], write_call["args"], err_msg, False
                    )
                    return ""

                # Stage the *resolved* args (with record id), with a fresh
                # nonce embedded in the Yes/No button payload — the
                # confirmation handler verifies the click is bound to this
                # specific staged write.
                nonce = session.sudo().stage_pending(
                    write_call["name"], preflight["args"]
                )
                self.tg.send_confirmation(chat_id, preflight["question"], nonce=nonce)
                return ""  # Pause — wait for user's Yes/No

            if not read_results:
                return result["text"]

        return "I wasn't able to complete your request after several attempts."

    def execute_confirmed(self, chat_id: str, tool_name: str, args: dict) -> None:
        """Execute a write tool after the user confirmed via inline keyboard."""
        error_msg = None
        try:
            result = execute_tool(self.env, tool_name, args)
            success = True
        except Exception as e:
            result = f"Error executing {tool_name}: {e}"
            success = False
            error_msg = str(e)
            _logger.exception(
                "Confirmed tool %s failed for chat %s", tool_name, chat_id
            )

        self.tg.send_message(chat_id, result)
        self._audit(chat_id, tool_name, args, result, success, error_msg=error_msg)

        # Append result to session history so the LLM has context in the next turn
        session = (
            self.env["odoopilot.session"]
            .sudo()
            .search(
                [("channel", "=", self.channel), ("chat_id", "=", chat_id)],
                limit=1,
            )
        )
        if session:
            session.append_message("assistant", result)

    def _audit(
        self,
        chat_id: str,
        tool_name: str,
        tool_args: dict,
        result: str,
        success: bool,
        error_msg: str | None = None,
    ) -> None:
        try:
            self.env["odoopilot.audit"].sudo().create(
                {
                    "timestamp": fields.Datetime.now(),
                    "user_id": self.env.uid,
                    "channel": self.channel,
                    "tool_name": tool_name,
                    "tool_args": json.dumps(tool_args)[:500],
                    "result_summary": result[:500],
                    "success": success,
                    "error_message": error_msg or "",
                }
            )
        except Exception:
            pass  # Audit failure must never break the main flow
