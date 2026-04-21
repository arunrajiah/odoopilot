# Adding an LLM provider

OdooPilot normalises all LLM communication behind `BaseLLMProvider`. Adding a new provider is a matter of implementing one async method.

## Steps

### 1. Create the provider module

```python
# odoopilot/agent/providers/myprovider.py
from odoopilot.agent.providers.base import BaseLLMProvider, LLMResponse, Message, ToolSchema


class MyProvider(BaseLLMProvider):
    """Provider for MyLLM service."""

    def __init__(self, api_key: str, model: str = "my-model-v1") -> None:
        self.client = MyLLMClient(api_key=api_key)
        self.model = model

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> LLMResponse:
        # Convert internal Message/ToolSchema to provider format
        # Call the provider API
        # Convert the response back to LLMResponse
        ...
```

### 2. Register the provider

In `odoopilot/agent/providers/__init__.py`, add to `PROVIDER_REGISTRY`:

```python
from odoopilot.agent.providers.myprovider import MyProvider

PROVIDER_REGISTRY = {
    "openai": ...,
    "anthropic": ...,
    "ollama": ...,
    "groq": ...,
    "myprovider": MyProvider,  # add here
}
```

### 3. Add config support

In `odoopilot/config.py`, add any new env vars your provider needs and wire them into `build_llm_provider()`.

### 4. Write a test

```python
# tests/test_providers/test_myprovider.py
import pytest
from unittest.mock import AsyncMock, patch
from odoopilot.agent.providers.myprovider import MyProvider
from odoopilot.agent.providers.base import Message


@pytest.mark.asyncio
async def test_chat_returns_text():
    provider = MyProvider(api_key="test-key")
    with patch.object(provider, "client") as mock_client:
        mock_client.chat.return_value = ...  # mock provider response
        response = await provider.chat(
            messages=[Message(role="user", content="Hello")],
            tools=[],
        )
    assert response.text == "Hello from MyLLM"
```

### 5. Document it

Add a row to the provider table in [README.md](../README.md).

## Internal schemas

```python
@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None  # for tool result messages
    tool_calls: list[ToolCallRequest] | None = None  # for assistant messages with calls

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict  # JSON Schema object

@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCallRequest]  # empty list if no tool calls
```
