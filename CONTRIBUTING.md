# Contributing to OdooPilot

Thank you for helping make OdooPilot better. This guide gets you from zero to a merged PR as quickly as possible.

## Your first contribution

The fastest path is implementing a missing Odoo tool. Here's the full loop:

### 1. Pick a tool

Open [README.md](README.md) and find a tool marked as unimplemented in the domain table, or check open issues labelled `good first issue`.

### 2. Set up your environment

```bash
git clone https://github.com/arunrajiah/odoopilot.git
cd odoopilot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Implement the tool

Follow the guide in [docs/adding-a-tool.md](docs/adding-a-tool.md). The short version:

1. Create (or add to) the relevant domain file under `odoopilot/agent/tools/`.
2. Subclass `BaseTool`, define `name`, `description`, and `parameters` (Pydantic schema).
3. Implement `execute(self, odoo, user_id, **kwargs)`.
4. Register the tool in `odoopilot/agent/tools/__init__.py`.
5. Write a test in `tests/test_tools/`.
6. Add one line to the example table in `docs/adding-a-tool.md`.

### 4. Run CI locally

```bash
ruff check .
ruff format --check .
mypy odoopilot/
pytest
```

All four must be green before opening a PR.

### 5. Open a PR

- Title: `feat(tools): add <tool_name> to <domain>` (Conventional Commits)
- Body: what the tool does, which Odoo model it touches, and how you tested it
- Link the issue if there is one

A maintainer will review within a few days.

---

## Guidelines

### Code style
- `ruff` for linting and formatting (no black, no isort)
- Strict `mypy` — no `Any` unless truly unavoidable, annotate it with a comment
- No comments that explain *what* the code does — only *why* when non-obvious

### Tool rules (non-negotiable)
- Every tool must have: a docstring, a Pydantic input schema, a test, and a line in the docs table
- Read tools execute immediately; write tools must call `require_confirmation()` before mutating Odoo
- All tool calls are audit-logged automatically via the agent loop — don't add extra logging inside tools
- No hardcoded user-facing strings — use the response helpers so strings can be i18n-ed later

### Provider rules
- No OpenAI-only code paths. If a feature only works on one provider, it's not ready
- New providers: subclass `BaseLLMProvider`, implement `chat()`, add to `PROVIDER_REGISTRY`

### Commit format
We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(tools): add confirm_sale_order write tool
fix(telegram): handle edited messages gracefully
docs(adding-a-tool): add hr domain examples
chore(ci): pin python-telegram-bot to 20.7
```

### Licensing
All contributions are licensed under LGPL-3.0-or-later. By submitting a PR you confirm you have the right to do so.

---

## Getting help

Open a [GitHub Discussion](https://github.com/arunrajiah/odoopilot/discussions) — we're friendly.
