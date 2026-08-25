"""Tests for the OpenRouter model catalog sync and settings picker."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

PAYLOAD = {
    "data": [
        {
            "id": "openai/gpt-4o-mini",
            "name": "GPT-4o Mini",
            "context_length": 128000,
            "architecture": {"modality": "text->text"},
        },
        {
            "id": "foo/imagegen",
            "name": "Imager",
            "architecture": {"modality": "text->image"},
        },
        {
            "id": "anthropic/claude-3.5-haiku",
            "name": "Claude 3.5 Haiku",
            "architecture": {"modality": "text+image->text"},
        },
    ]
}


def _mock_response():
    resp = MagicMock()
    resp.json.return_value = PAYLOAD
    resp.raise_for_status.return_value = None
    return resp


class TestAiModelCatalog(TransactionCase):
    def setUp(self):
        super().setUp()
        self.admin = self.env.ref("base.user_admin")
        self.Catalog = self.env["odoopilot.ai.model"].with_user(self.admin)

    def _sync(self):
        with patch(
            "odoo.addons.odoopilot.models.odoopilot_ai_model.requests.get",
            return_value=_mock_response(),
        ):
            return self.Catalog.sync_openrouter()

    def test_sync_filters_and_upserts(self):
        self.assertEqual(self._sync(), 2)  # image generator filtered out
        self.assertEqual(self._sync(), 2)  # idempotent re-sync, no duplicates
        recs = self.Catalog.search([("provider", "=", "openrouter")])
        self.assertEqual(len(recs), 2)
        mini = recs.filtered(lambda r: r.code == "openai/gpt-4o-mini")
        self.assertEqual(mini.context_length, 128000)
        self.assertIn("(openai/gpt-4o-mini)", mini.display_name)

    def test_sync_requires_admin(self):
        internal = self.env["res.users"].with_context(
            no_reset_password=True
        ).create({"name": "OP Plain", "login": "op_plain_catalog_test"})
        with self.assertRaises(UserError):
            self.env["odoopilot.ai.model"].with_user(internal).sync_openrouter()

    def test_picker_fills_model_override(self):
        self._sync()
        mini = self.Catalog.search([("code", "=", "openai/gpt-4o-mini")])
        settings = (
            self.env["res.config.settings"]
            .with_user(self.admin)
            .new({"odoopilot_llm_provider": "openrouter"})
        )
        settings.odoopilot_llm_openrouter_model_id = mini
        settings._onchange_odoopilot_llm_openrouter_model_id()
        self.assertEqual(settings.odoopilot_llm_model, "openai/gpt-4o-mini")
