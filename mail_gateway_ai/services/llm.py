import json
import logging

import requests

_logger = logging.getLogger(__name__)

# Default models per provider
DEFAULTS = {
    "anthropic": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-70b-versatile",
}

OPENAI_COMPAT_BASE = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}


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
        resp.raise_for_status()
        data = resp.json()

        # Normalise to internal format: {stop_reason, text, tool_calls}
        stop_reason = data.get("stop_reason")
        text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "args": block.get("input", {}),
                })

        return {"stop_reason": stop_reason, "text": text.strip(), "tool_calls": tool_calls, "raw": data}

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
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "tools": openai_tools, "max_tokens": 1024},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        text = msg.get("content") or ""
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            tool_calls.append({
                "id": tc["id"],
                "name": tc["function"]["name"],
                "args": json.loads(tc["function"]["arguments"] or "{}"),
            })
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return {"stop_reason": stop_reason, "text": text.strip(), "tool_calls": tool_calls, "raw": data}

    def build_tool_result_messages(self, tool_calls: list, results: list, provider: str = None) -> list:
        """Build the messages to append after tool execution."""
        provider = provider or self.provider
        msgs = []
        if provider == "anthropic":
            # Anthropic expects an assistant message with tool_use blocks followed by user message with tool_result blocks
            assistant_content = [
                {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]}
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
            msgs.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                    for tc in tool_calls
                ],
            })
            for tc, result in zip(tool_calls, results):
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
        return msgs
