"""Tests for provider payload formatting in the LLM adapter."""

from unittest.mock import patch

from requests import HTTPError

from odoo.tests.common import TransactionCase

from ..services.llm import LLMClient


class TestOpenAICompatToolResultMessages(TransactionCase):
    """Groq is strict about OpenAI-compatible tool message shape."""

    def test_tool_result_messages_match_groq_expected_shape(self):
        client = LLMClient("groq", "gsk_test")
        tool_calls = [
            {
                "id": "call_123",
                "name": "get_my_tasks",
                "args": {"limit": 3},
            }
        ]

        messages = client.build_tool_result_messages(tool_calls, ["Tasks: none"])

        self.assertEqual(messages[0]["role"], "assistant")
        self.assertNotIn("content", messages[0])
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "call_123")
        self.assertEqual(
            messages[0]["tool_calls"][0]["function"]["arguments"], '{"limit": 3}'
        )
        self.assertEqual(
            messages[1],
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "name": "get_my_tasks",
                "content": "Tasks: none",
            },
        )


class TestOpenAICompatToolCallParsing(TransactionCase):
    def test_null_tool_arguments_become_empty_mapping(self):
        client = LLMClient("groq", "gsk_test")

        class DummyResponse:
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "call_123",
                                        "function": {
                                            "name": "get_sale_orders",
                                            "arguments": "null",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }

        with patch("odoo.addons.odoopilot.services.llm.requests.post") as post:
            post.return_value = DummyResponse()
            result = client.chat([{"role": "user", "content": "sales"}], [])

        self.assertEqual(
            result["tool_calls"],
            [{"id": "call_123", "name": "get_sale_orders", "args": {}}],
        )

    def test_malformed_tool_arguments_become_empty_mapping(self):
        client = LLMClient("groq", "gsk_test")

        class DummyResponse:
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "call_bad",
                                        "function": {
                                            "name": "get_sale_orders",
                                            "arguments": "{not-json",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }

        with patch("odoo.addons.odoopilot.services.llm.requests.post") as post:
            post.return_value = DummyResponse()
            result = client.chat([{"role": "user", "content": "sales"}], [])

        self.assertEqual(
            result["tool_calls"],
            [{"id": "call_bad", "name": "get_sale_orders", "args": {}}],
        )

    def test_groq_tool_use_failed_generation_is_recovered(self):
        client = LLMClient("groq", "gsk_test")
        tools = [
            {
                "name": "get_sale_orders",
                "description": "List sale orders.",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

        class DummyResponse:
            text = (
                '{"error":{"code":"tool_use_failed",'
                '"failed_generation":"<function=get_sale_orders":'
                '{\\"limit\\":\\"1\\"}</function>"}}'
            )

            def raise_for_status(self):
                raise HTTPError("400 Client Error")

            def json(self):
                return {
                    "error": {
                        "message": "Failed to call a function.",
                        "code": "tool_use_failed",
                        "failed_generation": (
                            '<function=get_sale_orders":{"limit":"1"}</function>'
                        ),
                    }
                }

        with patch("odoo.addons.odoopilot.services.llm.requests.post") as post:
            post.return_value = DummyResponse()
            result = client.chat([{"role": "user", "content": "one sale"}], tools)

        self.assertEqual(result["stop_reason"], "tool_use")
        self.assertEqual(
            result["tool_calls"],
            [
                {
                    "id": "call_failed_generation_0",
                    "name": "get_sale_orders",
                    "args": {"limit": "1"},
                }
            ],
        )
        self.assertTrue(result["raw"]["recovered"])

    def test_groq_tool_use_failed_unknown_tool_still_raises(self):
        client = LLMClient("groq", "gsk_test")
        tools = [
            {
                "name": "get_sale_orders",
                "description": "List sale orders.",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

        class DummyResponse:
            text = '{"error":{"code":"tool_use_failed"}}'

            def raise_for_status(self):
                raise HTTPError("400 Client Error")

            def json(self):
                return {
                    "error": {
                        "code": "tool_use_failed",
                        "failed_generation": (
                            '<function=delete_everything>{"limit":1}</function>'
                        ),
                    }
                }

        with patch("odoo.addons.odoopilot.services.llm.requests.post") as post:
            post.return_value = DummyResponse()
            with self.assertRaises(HTTPError):
                client.chat([{"role": "user", "content": "one sale"}], tools)


class TestLLMHTTPErrorScrubbing(TransactionCase):
    def test_http_error_includes_body_but_redacts_api_key(self):
        client = LLMClient("groq", "gsk_secret")

        class DummyResponse:
            text = '{"error":"bad key gsk_secret"}'

            def raise_for_status(self):
                raise HTTPError("400 Client Error")

        with self.assertRaises(HTTPError) as cm:
            client._raise_for_status(DummyResponse())

        msg = str(cm.exception)
        self.assertIn("Response body", msg)
        self.assertIn("***", msg)
        self.assertNotIn("gsk_secret", msg)
