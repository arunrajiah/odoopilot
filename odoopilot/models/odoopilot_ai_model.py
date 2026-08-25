"""Synced AI model catalog so admins can pick a model instead of typing ids."""

import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OdoopilotAiModel(models.Model):
    _name = "odoopilot.ai.model"
    _description = "OdooPilot AI Model Catalog Entry"
    _order = "name, code"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True)
    code = fields.Char(
        required=True, index=True,
        help="Provider model id, e.g. openai/gpt-4o-mini",
    )
    provider = fields.Selection(
        [("openrouter", "OpenRouter")], required=True, default="openrouter"
    )
    context_length = fields.Integer(string="Context Length")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "code_provider_uniq",
            "unique(provider, code)",
            "This model is already in the catalog.",
        ),
    ]

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name and rec.name != rec.code:
                rec.display_name = "%s (%s)" % (rec.name, rec.code)
            else:
                rec.display_name = rec.name or rec.code or ""

    @api.model
    def sync_openrouter(self):
        """Fetch the public OpenRouter catalog (no API key needed) and upsert
        text-output models. Returns the number of catalog entries synced."""
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only administrators may sync the model list."))
        try:
            resp = requests.get(
                "https://openrouter.ai/api/v1/models", timeout=20
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data") or []
        except (requests.RequestException, ValueError) as exc:
            raise UserError(
                _("Could not fetch the OpenRouter model list: %s") % exc
            )
        if not data:
            raise UserError(_("OpenRouter returned an empty model list."))
        Model = self.sudo().with_context(active_test=False)
        existing = {
            r.code: r for r in Model.search([("provider", "=", "openrouter")])
        }
        seen, count = set(), 0
        for m in data:
            code = m.get("id")
            if not code or code in seen:
                continue
            modality = (m.get("architecture") or {}).get(
                "modality"
            ) or "text->text"
            if not modality.endswith("->text"):
                continue  # image/audio generators cannot run the agent loop
            seen.add(code)
            vals = {
                "name": m.get("name") or code,
                "code": code,
                "provider": "openrouter",
                "active": True,
                "context_length": int(m.get("context_length") or 0),
            }
            rec = existing.get(code)
            if rec:
                rec.write(vals)
            else:
                Model.create(vals)
            count += 1
        return count
