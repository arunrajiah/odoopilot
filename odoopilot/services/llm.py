import json
import logging
import re

import requests
from requests import HTTPError

_logger = logging.getLogger(__name__)

# Default models per provider
DEFAULTS = {
    "anthropic": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
}

OPENAI_COMPAT_BASE = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}


def _normalise_tool_args(args) -> dict:
    """Return a mapping for tool kwargs even when providers emit null."""
    return args if isinstance(args, dict) else {}


def _parse_tool_args(raw: str) -> dict:
    """Parse provider tool arguments and tolerate malformed/empty payloads."""
    try:
        return _normalise_tool_args(json.loads(raw or "{}"))
    except (TypeError, ValueError):
        _logger.warning("LLM returned malformed tool arguments: %r", raw)
        return {}


def _parse_failed_generation_tool_call(failed_generation: str, tool_names: set):
    """Recover a tool call from Groq's tool_use_failed error detail."""
    if not failed_generation:
        return None
    patterns = (
        r"<function=([A-Za-z_][A-Za-z0-9_]*)>(.*?)</function>",
        r"<function=([A-Za-z_][A-Za-z0-9_]*)\"?:(.*?)</function>",
    )
    for pattern in patterns:
        match = re.search(pattern, failed_generation, flags=re.DOTALL)
        if not match:
            continue
        name, raw_args = match.groups()
        if name not in tool_names:
            _logger.warning(
                "Ignoring failed_generation for unknown tool %s: %r",
                name,
                failed_generation,
            )
            return None
        return {
            "id": "call_failed_generation_0",
            "name": name,
            "args": _parse_tool_args(raw_args.strip()),
        }
    return None


class LLMClient:
    def __init__(self, provider: str, api_key: str, model: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.model = model or DEFAULTS.get(provider, "")

    def chat(self, messages: list, tools: list) -> dict:
        """Send messages + tools to LLM. Returns parsed response dict."""
        if self.provider == "anthropic":
            return self._call_anthropic(messages, tools)
        return self._call_openai_compat(messages, tools)

    def _scrub(self, text: str) -> str:
        """Remove provider secrets from error strings before logging/raising."""
        if not text:
            return ""
        scrubbed = str(text)
        if self.api_key:
            scrubbed = scrubbed.replace(self.api_key, "***")
        return scrubbed

    def _raise_for_status(self, resp):
        """Raise HTTP errors with the provider response body preserved."""
        try:
            resp.raise_for_status()
        except HTTPError as exc:
            body = self._scrub(resp.text or "")
            msg = f"{exc}. Response body: {body[:1000]}"
            raise HTTPError(msg, response=resp) from exc

    def _call_anthropic(self, messages: list, tools: list) -> dict:
        # Extract system message if present
        system = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                chat_msgs.append(m)

        anthropic_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": chat_msgs,
            "tools": anthropic_tools,
        }
        if system:
            payload["system"] = system

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        self._raise_for_status(resp)
        data = resp.json()

        # Normalise to internal format: {stop_reason, text, tool_calls}
        stop_reason = data.get("stop_reason")
        text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block["id"],
                        "name": block["name"],
                        "args": _normalise_tool_args(block.get("input", {})),
                    }
                )

        return {
            "stop_reason": stop_reason,
            "text": text.strip(),
            "tool_calls": tool_calls,
            "raw": data,
        }

    def _recover_failed_tool_call(self, resp, tools: list) -> dict | None:
        """Convert Groq tool_use_failed responses into internal tool calls."""
        try:
            error = (resp.json() or {}).get("error", {})
        except (TypeError, ValueError):
            return None
        if error.get("code") != "tool_use_failed":
            return None
        tool_names = {tool["name"] for tool in tools}
        tool_call = _parse_failed_generation_tool_call(
            error.get("failed_generation") or "", tool_names
        )
        if not tool_call:
            return None
        _logger.warning(
            "Recovered Groq tool_use_failed response as local tool call: %s",
            tool_call["name"],
        )
        return {
            "stop_reason": "tool_use",
            "text": "",
            "tool_calls": [tool_call],
            "raw": {"error": error, "recovered": True},
        }

    def _call_openai_compat(self, messages: list, tools: list) -> dict:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]
        url = OPENAI_COMPAT_BASE.get(self.provider, OPENAI_COMPAT_BASE["openai"])
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "tools": openai_tools,
                "max_completion_tokens": 1024,
            },
            timeout=30,
        )
        try:
            self._raise_for_status(resp)
        except HTTPError:
            recovered = self._recover_failed_tool_call(resp, tools)
            if recovered:
                return recovered
            raise
        data = resp.json()

        if "choices" not in data or not data["choices"]:
            error = data.get("error", {})
            raise RuntimeError(error.get("message", "LLM API returned no choices"))
        choice = data["choices"][0]
        msg = choice["message"]
        text = msg.get("content") or ""
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            tool_calls.append(
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "args": _parse_tool_args(tc["function"].get("arguments")),
                }
            )
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return {
            "stop_reason": stop_reason,
            "text": text.strip(),
            "tool_calls": tool_calls,
            "raw": data,
        }

    def build_tool_result_messages(
        self, tool_calls: list, results: list, provider: str = None
    ) -> list:
        """Build the messages to append after tool execution."""
        provider = provider or self.provider
        msgs = []
        if provider == "anthropic":
            # Anthropic expects an assistant message with tool_use blocks followed by user message with tool_result blocks
            assistant_content = [
                {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["args"],
                }
                for tc in tool_calls
            ]
            user_content = [
                {"type": "tool_result", "tool_use_id": tc["id"], "content": str(result)}
                for tc, result in zip(tool_calls, results)
            ]
            msgs.append({"role": "assistant", "content": assistant_content})
            msgs.append({"role": "user", "content": user_content})
        else:
            # OpenAI format
            msgs.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc, result in zip(tool_calls, results):
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": str(result),
                    }
                )
        return msgs
