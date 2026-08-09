# OdooPilot
Odoo addon that gives every employee an AI assistant on Telegram/WhatsApp: apply for leave, approve requests, update CRM, check stock without opening Odoo. LGPL-3, targets Odoo 17.0 and 18.0 Community (manifest version 17.0.23.0.0).

## Stack
- Odoo addon, Python 3 (.venv present)
- Standard Odoo layout: models/views/security/static + controllers and services
- pytest (+ coverage), ruff, mypy, pre-commit, pylint-odoo conventions

## Layout
- `odoopilot/` - the addon: `__manifest__.py`, models/, views/, controllers/, services/, security/, data/, migrations/, static/, tests/, readme/ (OCA-style fragments)
- `scripts/` - dev/release helper scripts
- Root: CONTRIBUTING.md, SECURITY.md, CHANGELOG.md

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
- `.venv/bin/ruff check odoopilot/` and `.venv/bin/ruff format --check odoopilot/` - exactly what CI runs
- `.venv/bin/mypy odoopilot/` - type-check
- `python3 scripts/check_listing_rendering.py` - App Store description must survive Odoo's HTML sanitiser
- `pre-commit run -a` - full hook suite
- Module install/upgrade requires a running Odoo instance: `odoo -u odoopilot` (side effect: alters DB)

### Tests: pytest does NOT run them
Every file in `odoopilot/tests/` is an Odoo `TransactionCase` and imports
`odoo`, so plain `pytest` fails at collection. They need a real Odoo install
plus PostgreSQL:
`odoo-bin -d <db> --addons-path=<odoo>/addons,<repo-root> -i odoopilot --test-enable --stop-after-init`
The `Odoo module tests` CI job does this on every push and PR; it is the only
place the suite runs automatically.

### Tool versions are pinned in three places
`ruff==0.4.4` and `mypy==1.10.0` in `requirements-dev.txt`, `.github/workflows/ci.yml`
and `.pre-commit-config.yaml`. Bump all three together. A newer ruff reports
errors CI does not, so a version drift looks like a code problem and isn't.

## Conventions
- OCA-style structure and pylint-odoo compliance; readme/ fragments generate README.rst.
- Migrations under migrations/ per version bump; bump manifest version with schema changes.
- No em dashes in user-facing copy.

## Token efficiency
- Grep/Glob to the target file; read only the relevant section, never whole large files.
- Don't re-read files after editing. Verify once per batch of edits, not per edit.
- Keep progress narration and final summaries to 2-3 sentences.
