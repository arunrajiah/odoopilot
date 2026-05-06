# OCA submission checklist

This file documents what's been done in OdooPilot to align with [OCA](https://odoo-community.org/) module-quality standards, and what an OCA reviewer would still need to confirm in a PR.

The plan is to submit the module to a relevant OCA repository (most likely [OCA/connector](https://github.com/OCA/connector) or a new dedicated AI-integration repo, depending on OCA's recommendation). Until that PR opens, the items below stand as a snapshot of where preparation is.

## Done

### Module structure
- [x] **Single module folder** at the repo root: `odoopilot/`
- [x] **`__manifest__.py`** with the OCA-required fields:
  - [x] `name`, `summary`, `version` (`<series>.<x>.<x>.<x>`), `license` (LGPL-3)
  - [x] `category` (from Odoo's standard list — `Discuss`)
  - [x] `author` includes "Odoo Community Association (OCA)" per OCA convention
  - [x] `maintainers: ["arunrajiah"]`
  - [x] `development_status: "Beta"` (matches the Odoo App Store listing)
  - [x] `application: True`
  - [x] No redundant `installable` or `auto_install` (both at default values)
  - [x] `data` lists views and the cron file in load order
  - [x] `images` lists the App Store banner
- [x] **`README.rst`** generated from `odoopilot/readme/` per OCA's
  [`oca-gen-addon-readme`](https://github.com/OCA/maintainer-tools) convention:
  - [x] `DESCRIPTION.rst`, `INSTALL.rst`, `CONFIGURE.rst`, `USAGE.rst`,
        `ROADMAP.rst`, `CONTRIBUTORS.rst`, `CREDITS.rst`, `MAINTAINERS.rst`
  - [x] All written in reStructuredText, not Markdown
- [x] **`static/description/icon.png`** present (84×84)
- [x] **`static/description/index.html`** App Store listing
- [x] **`security/ir.model.access.csv`** with explicit ACLs for every model

### Code quality
- [x] **`pylint --load-plugins=pylint_odoo --enable=odoolint odoopilot/`** scores **10.00/10** with one intentional `noqa: C8103` (manifest description, kept for App Store search indexing)
- [x] **`ruff format --check`** clean
- [x] **`ruff check`** clean
- [x] **`bandit -r odoopilot -ll -ii`** — 0 medium/high findings
- [x] **`semgrep --config=p/python`** — 0 blocking findings
- [x] All XML files well-formed (CI job)
- [x] No `attrs=` or `states=` on view elements (removed in 17+)
- [x] No raw `_(f"...")` f-strings inside translation calls — uses lazy `self.env._("text %s", arg)` form
- [x] No bare `except: pass` — all caught exceptions log at WARNING

### Tests
- [x] **`odoopilot/tests/`** with `TransactionCase` coverage:
  - `test_security.py` — webhook auth, nonce, link tokens, rate limit, dedup
  - `test_admin_views.py` — computed activity-summary fields
  - `test_employee_tools.py` — tool-registry hygiene, preflight validation, employee_id rebinding
  - `test_scope_guard.py` — pattern coverage + Unicode/foreign-language bypasses
  - `test_voice.py` — STT client, duration cap, voice gate
- [x] **~2,500 lines of regression tests** across 6 security releases

### Documentation
- [x] **`README.md`** at repo root with banner, install, architecture diagram, sizing & capacity, security model, status & roadmap
- [x] **`CHANGELOG.md`** at repo root, [Keep a Changelog](https://keepachangelog.com/) format, every release entry
- [x] **`SECURITY.md`** with private disclosure policy + supported-versions table
- [x] **`CODE_OF_CONDUCT.md`**, **`CONTRIBUTING.md`** at repo root

### Branches
- [x] **`17.0`** branch live on Odoo App Store at `apps.odoo.com/apps/modules/17.0/odoopilot`
- [x] **`18.0`** branch live on Odoo App Store at `apps.odoo.com/apps/modules/18.0/odoopilot`
- [x] Both branches receive security backports

### Security posture
- [x] Public security audit (April 2026, u/jeconti on r/Odoo) closed in `v17.0.7.0.0`
- [x] Three follow-up internal reviews closed in `v17.0.8`, `v17.0.9`, `v17.0.15`
- [x] Webhook signatures verified in constant time (HMAC for WhatsApp, secret token for Telegram)
- [x] Per-write nonce on confirmation buttons defeats prompt-injection swap
- [x] Magic-link tokens hashed at rest (SHA-256), single-use, 1-hour TTL, CSRF-protected flow
- [x] Scope guard refuses off-topic / extraction / jailbreak requests pre-LLM
- [x] CI runs `bandit` and `semgrep` on every push

## Pending (the OCA PR itself)

- [ ] Pick the target OCA repository. Probably worth posting in the [OCA forum](https://github.com/OCA/maintainer-tools/discussions) or the OCA Mattermost first to get a recommendation; possible candidates:
  - `OCA/connector` (event-bus framework — fit isn't perfect)
  - `OCA/server-tools` (general Odoo tooling — wide remit)
  - A new repo (would require OCA board approval)
- [ ] Open the PR, run OCA's CI (`oca-port`, `runboat`), address review comments
- [ ] If accepted: rename `author` to `"arunrajiah, Odoo Community Association (OCA)"` (already done preemptively to satisfy pylint), and the module's git history will move to the OCA org
- [ ] Add the OCA repo to the `apps.odoo.com` listing's "Source" field

## Out of scope (we don't need these to submit)

- [ ] Translation `.po` files. We use only English in the source today; OCA accepts modules without translation files (the Weblate integration generates them later).
- [ ] An icon contributed via [OCA's icon library](https://github.com/OCA/iso). Our custom icon is fine.
- [ ] OCA pre-commit hook config. We have our own `.pre-commit-config.yaml`; OCA will normalise it to their standard during their review.

## Reviewer quick-check

A reviewer can verify the prep status with:

```bash
git clone -b 17.0 https://github.com/arunrajiah/odoopilot.git
cd odoopilot

# Static checks
ruff format --check odoopilot/
ruff check odoopilot/
pylint --load-plugins=pylint_odoo --rcfile=/dev/null \
    --disable=all --enable=odoolint odoopilot/

# OCA structure
ls odoopilot/readme/        # Eight RST files
cat odoopilot/__manifest__.py | head -30
```

Expected output: ruff clean, pylint-odoo 10.00/10 (with one intentional `# noqa: C8103` in the manifest), readme/ has the eight OCA-template RST files, manifest carries `maintainers: ["arunrajiah"]` and `application: True`.
