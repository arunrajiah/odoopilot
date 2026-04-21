# Changelog

All notable changes to OdooPilot are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial repo scaffold
- Channel adapter abstraction (base + Telegram implementation)
- LLM provider abstraction (OpenAI + Anthropic)
- Odoo JSON-RPC client
- `find_product` inventory tool (first read tool)
- Minimal agent loop (message → LLM → tool → response)
- FastAPI webhook entrypoint
- SQLite storage with SQLAlchemy 2.x + Alembic
- Audit log for all tool calls
- Identity/user linking scaffold
- Companion Odoo addon scaffold (`mail_gateway_ai`)
- Docker Compose example (Odoo + OdooPilot + Postgres)
- CI workflow (ruff, mypy, pytest)
