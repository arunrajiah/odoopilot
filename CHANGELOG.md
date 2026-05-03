# Changelog

All notable changes to OdooPilot are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

The `17.0.x` series ships from the [`17.0` branch](https://github.com/arunrajiah/odoopilot/tree/17.0).  
The `18.0.x` series ships from the [`18.0` branch](https://github.com/arunrajiah/odoopilot/tree/18.0).

---

## [18.0.3.0.0] — 2026-05-03 — Employee-self-service tools backport

Mirrors **17.0.14.0.0** to the 18 series. Six new tools widen the
bot's audience: `find_partner` (read), `clock_in`, `clock_out`,
`submit_expense`, `submit_timesheet`, `create_calendar_event`. Tool
count on the 18 branch: 13 → 19. Same code, same tests, same
registry-hygiene guarantees as the 17 release.

The 18 series stays in **Alpha** until an operator validates an
end-to-end install on a real Odoo 18 instance.

---

## [18.0.2.0.0] — 2026-05-03 — Scope guard backport

Mirrors **17.0.13.0.0** to the 18 series. Adds the pre-LLM regex
filter (`services/scope_guard.py`) and the hardened `SYSTEM_PROMPT`
that refuse off-topic / extraction / jailbreak attempts before paying
for an LLM call. See the [17.0.13.0.0 entry below](#17013--2026-05-03--scope-guard-refuse-off-topic-requests)
for the full description — same code, same tests, same configuration
flag (`odoopilot.scope_guard_enabled`).

The 18 series stays in **Alpha** until an operator validates an
end-to-end install on a real Odoo 18 instance.

---

## [18.0.1.0.0] — 2026-05-02 — Odoo 18 port (Alpha)

First release on the new `18.0` branch. **Functionally identical to
17.0.12.0.0** — same security model, same admin views, same tools,
same agent loop. The version number resets to `18.0.1.0.0` per Odoo's
versioning convention (one series per Odoo major version).

### Why Alpha

We have not yet had an operator validate an end-to-end install on a
running Odoo 18 instance. Static analysis is clean (ruff format, ruff
check, bandit, semgrep, listing renderable, all view XML well-formed)
and we audited for the known 17→18 breaking patterns:

- All views already use ``<list>`` (the 17+ form). No ``<tree>``.
- No ``attrs=`` or ``states=`` on view elements.
- No JS / Owl code.
- ``read_group`` (deprecated in 18, used by the identity activity-summary
  fields) still works in 18; removal is slated for 19. We will migrate
  to ``_read_group`` ahead of that release.

### Known unknowns

The risk surface that we cannot statically verify is the ORM tool layer
in ``services/tools.py`` — for tools that touch upstream models
(``project.task``, ``sale.order``, ``crm.lead``, ``hr.leave``,
``account.move``, ``stock.picking``, ``purchase.order``, ``hr.employee``)
field renames in 18 could break individual tool calls without breaking
module install. If you hit one, please open an issue with the tool name
and the exception text.

### Branch policy

- `17.0` continues to receive backports of any security fix that lands
  on `18.0`. The 17 branch is supported through Odoo's own 17 LTS
  window.
- `main` continues to track `17.0` for now, since that is where most
  installs live. We will promote `main` → `18.0` once the 18 series
  reaches Beta.

---

## [17.0.12.0.0] — 2026-05-02 — Operator admin views

The post-install experience for the operator who installed the addon now
matches the production-ready security model. The bare list views that
shipped historically have been replaced with a proper admin dashboard
the operator can scan in two seconds.

### Added — Activity-summary fields on `odoopilot.identity`

Three live-computed fields read from the audit table for each linked
user, with a 7-day sliding window:

- `last_activity` — datetime of the most recent audit row for this
  ``(user_id, channel)`` pair (or empty if never used).
- `message_count_7d` — count of audit rows in the window.
- `success_rate_7d` — % of those that succeeded.

Computed via two ``read_group`` calls per recordset (no N+1), gated by
``compute_sudo=True`` so the system-only audit table can be read for any
identity the operator can see.

### Added — Redesigned Linked Users view

`Settings → OdooPilot → Linked Users` (renamed from "User Identities"):

- New columns for ``last_activity``, ``message_count_7d``,
  ``success_rate_7d``.
- Row decoration: green when the user has been active in the window,
  muted when never used or unlinked.
- Search filters: *Active in last 7 days*, *Linked but never used*,
  *Telegram* / *WhatsApp*, *Inactive (unlinked)*.
- Group-by: *User*, *Channel*, *Language*.
- Form view: smart-button stat tiles for messages and success rate, plus
  a ``View activity`` button in the header that opens the audit log
  filtered to this identity's user + channel.

### Added — Redesigned Audit Log view

`Settings → OdooPilot → Audit Log`:

- Row decoration: failures in red. Inline ``error_message`` column makes
  trouble visible without drilling into the form.
- Search filters: *Failures only*, *Successes only*, *Write actions*,
  *Read actions*, *Telegram*, *WhatsApp*, *Today*, *Last 7 days*.
- Group-by: *User*, *Tool*, *Channel*, *Outcome*, *Day*.
- Default open: filtered to the last 7 days, grouped by day. The most
  common operator question is "what happened recently?", not "show me
  everything ever".
- Form view: title bar shows tool name + user + channel + timestamp; a
  notebook splits the result and the JSON arguments into separate tabs.

### Tests

- New `tests/test_admin_views.py` with 7 tests covering the computed
  field semantics: empty state, window cutoff at 7 days, success-rate
  rounding, channel isolation, user isolation, and the
  ``action_view_audit`` button payload.

---

## [17.0.11.0.0] — 2026-05-02 — Polish pass: banner, CI hardening, listing linter

A non-security release. Three engineering hygiene items shipped together.
Operator upgrade is optional — no code paths changed.

### Added — Banner regenerated to match the new pitch

`static/description/banner.png` redesigned to lead with the headline the
listing now uses: "Your team uses Odoo — without logging in to Odoo."
Big typography on the left; two phone notifications on the right
showing the leave-request → approval flow (WhatsApp filing, Telegram
approving). Source HTML and a Playwright render script live in
`scripts/render_banner.py` so the image can be regenerated on demand.

### Added — Static security scanning in CI

`.github/workflows/ci.yml` now runs `bandit` and `semgrep` on every
push and PR. After three security releases in a week, this is the
right insurance — the next class of issue gets surfaced automatically
rather than in a public Reddit post. Both scanners run with
`continue-on-error: true` while we tune the rule set; real findings
land in the job log without blocking unrelated PRs. We will tighten
to a hard gate once the noise floor is known.

### Added — App Store listing renderable check

A new CI job runs `scripts/check_listing_rendering.py` against
`static/description/index.html` and fails the build if any of the
three patterns the App Store sanitiser breaks reappears:

* `background:` or `background-color:` declarations in inline styles
* `color: #fff` / `color: white` text colours
* `<a >` tags around custom labels

A header comment in `index.html` documents the rules; the linter
enforces them so the listing cannot regress without somebody noticing.

### Local checks

- `bandit -r odoopilot -x odoopilot/tests -ll -ii` -- 0 medium/high
  findings.
- `semgrep --config=p/python` -- 0 blocking findings.
- `python3 scripts/check_listing_rendering.py` -- clean.

---

## [17.0.10.0.0] — 2026-04-28 — Repositioning + community panel + listing fix

A non-security release bundling three changes that shipped to `main` and
`17.0` over the last day. Upgrade is optional but recommended — the new
in-Odoo Settings panel in particular is worth pulling.

### Added — In-Odoo Settings community panel

Settings → OdooPilot now ends with a four-card action panel pointing at
the things users actually want to do after install:

- **Sponsor on GitHub** — `https://github.com/sponsors/arunrajiah`
- **Feedback & ideas** — opens a new GitHub Discussion in the Ideas
  category
- **Report a bug** — opens the GitHub issue template chooser
- **Report a security issue** — opens a private GitHub Security Advisory
  (the channel documented in `SECURITY.md`)

Plus a thin row of quick-reference links: source code, README,
CHANGELOG, security policy.

*File:* `views/res_config_settings_views.xml`.

### Fixed — App Store listing rendering

Inspecting the live page source revealed the Odoo App Store HTML
sanitiser does two things our previous listing relied on:

1. Strips every `background:` and `background-color:` declaration from
   inline `style=""` attributes (silently — the rest of the style
   survives).
2. Rewrites every `<a href="…">CustomText</a>` into
   `<span href="…">CustomText</span>` — which is non-clickable HTML.
   Plain URL text in the body is auto-linked by a separate pass that
   *does* survive the sanitiser.

Result before this fix: dark hero invisible (white text on white), CTA
buttons invisible, all custom-styled links non-functional. The listing
is now rebuilt for the sanitiser's actual rules:

- Zero `background` / `background-color` declarations. Visual hierarchy
  via borders, text colour, and padding only.
- Zero white text. All copy legible on the App Store's default page
  background.
- Zero styled `<a>` tags around custom labels. CTAs are now plain URL
  text with a leading label like "Get OdooPilot →"; the auto-linker
  makes them clickable.
- Demo conversation panes rebuilt with coloured left borders instead of
  background-filled chat bubbles.

A header comment in `index.html` documents the sanitiser's behaviour so
future edits don't regress.

*File:* `static/description/index.html`.

### Changed — Marketing repositioning

The pitch leads with a sharper frame: the killer use case is "your team
uses Odoo without logging in to Odoo," and the audience is your
internal team — not your customers. Updated across three surfaces, all
telling the same story:

- **App Store listing.** New hero headline; new "A day in the life"
  section with four employee scenarios (new hire applies for leave;
  manager approves; sales rep updates pipeline from the field; warehouse
  picker validates a transfer at the dock); new "What OdooPilot is not"
  callout; reframed personas; new "Odoo adoption problem — solved"
  before/after table.
- **Manifest.** Module name, summary, and long description rewritten.
  Search keywords expanded with employee-self-service, leave-request,
  approval, mobile-Odoo terms.
- **README.** Top section reframed to match. Demo conversation switched
  from a generic task query to the leave-request / approval flow that
  is now the canonical use case.

*Files:* `static/description/index.html`, `__manifest__.py`,
`README.md`.

---

## [17.0.9.0.0] — 2026-04-27 — Defence-in-depth pass

This release closes the four lower-impact findings from the post-17.0.7
internal review. None of these is independently exploitable in an isolated
attack scenario — they are hardening / hygiene fixes that remove easy
mistakes a future contributor could make. **No operator action required;
upgrade at your convenience.**

### Security — hardened (4)

- **Hygiene — Bot token redaction in logs.** Telegram bot URLs include the
  bot token (``…/bot<TOKEN>/sendMessage``). When ``requests`` raises an
  exception its ``str()`` typically includes the failing URL, so the bot
  token would land in the Odoo log where any operator with log access
  could see it. ``TelegramClient._scrub`` now redacts the token from any
  string before it reaches the logger; ``_call`` only logs the scrubbed
  message and the exception type, never the raw exception.
  *Files:* ``services/telegram.py``.

- **Hygiene — Constant-time compare for WhatsApp ``verify_token``.** The
  webhook-verification handshake compared the inbound ``hub.verify_token``
  with ``==``. Verify tokens are low-value (only used during webhook
  setup) and Meta retries quickly, so timing leakage was theoretical at
  best — but the cost of switching to ``hmac.compare_digest`` is zero and
  it removes one place a future timing-attack analysis would need to
  reason about.
  *Files:* ``controllers/main.py:whatsapp_verify``.

- **Defence-in-depth — Trust-boundary rename.** The two ``_dispatch_*``
  webhook helpers and their downstream ``_handle_*`` helpers received a
  parameter previously named ``env`` that was actually the bootstrap
  ``Environment(cr, SUPERUSER_ID, {})``. The agent loop correctly
  re-scoped to the linked user, but a future contributor adding a new
  tool path could easily forget. The parameter is now consistently named
  ``sudo_env`` throughout the dispatch tree, and a docstring on each
  dispatcher explains the trust boundary: ``sudo_env`` is for unavoidable
  privileged lookups (config, identity, session, link token); business-
  data access must use ``sudo_env(user=identity.user_id.id)``.
  *Files:* ``controllers/main.py``.

- **Defence-in-depth — Defensive ``else`` on malformed callback payloads.**
  ``_handle_confirmation`` and ``_handle_whatsapp_confirmation`` previously
  fell through to no-op when the parsed action was neither ``yes`` nor
  ``no``. Behaviour was correct but silent. They now log the malformed
  payload at WARNING and return explicitly, which makes it easier to spot
  bugs (or probe attempts) in the operator's log.
  *Files:* ``controllers/main.py``.

### Tests

Regression tests for the token-scrub behaviour and ``compare_digest``
semantics added in ``tests/test_security.py``.

---

## [17.0.8.0.0] — 2026-04-27 — Security release (follow-up audit)

After shipping `17.0.7.0.0` we ran an internal review to get ahead of any
issues the original auditor or others might still have. This release fixes
**three High** and **two Medium** findings from that review. **All
operators on 17.0.7.0.0 or earlier should upgrade.** No operator action
is required after upgrade — schema migrations are automatic.

### Security — fixed (5)

- **High — Magic-link CSRF.** The previous `/odoopilot/link/start` endpoint
  consumed the token on a single GET. An attacker could drop
  `<img src="…/odoopilot/link/start?token=ATTACKER_TOKEN">` into any record
  an admin would render (a CRM lead description, a mail comment, a customer
  note) and the admin's browser would silently link the attacker's chat to
  the admin's Odoo account. The flow is now two-step: GET renders a
  CSRF-protected confirmation page; POST (with `csrf_token`) is what
  consumes the token and writes the identity. Cross-site image GETs no
  longer cause any state change.
  *Files:* `controllers/main.py:link_start`, `controllers/main.py:link_confirm`,
  `views/link_pages.xml:link_confirm`,
  `models/odoopilot_link_token.py:peek`.

- **High — Identity hijack via stale link.** `link_start` previously
  overwrote `existing.user_id` on any logged-in visitor presenting a valid
  token, so a low-privilege user with a token could take over a higher-
  privilege user's existing chat link. The new code refuses to write when
  `existing.user_id` is set and differs from the current user — both at the
  GET preview and at POST commit time (race-safe). The legitimate owner
  must explicitly unlink first via the Identities admin view.
  *Files:* `controllers/main.py:link_start`, `controllers/main.py:link_confirm`.

- **High — Wildcard write-target hijack via prompt injection.** Write tools
  (`mark_task_done`, `confirm_sale_order`, `approve_leave`,
  `update_crm_stage`, `create_crm_lead`) previously resolved the target
  with `name ilike <LLM_string>` *at execute time*, while the confirmation
  prompt only showed the LLM's argument string. A poisoned record (a
  customer name like `"%"`, a task name with a single space) lured the
  LLM into supplying a wildcard-y argument, the user clicked Yes thinking
  they confirmed the LLM's stated record, and the executor mutated a
  different record entirely. Fix: `services/tools.py:preflight_write`
  resolves the target *before* staging, stores the resolved `res_id` in
  `pending_args`, and renders the resolved record's `display_name` in the
  confirmation prompt. Overly-short and wildcard-only names are rejected
  outright. CRM-stage lookups are now scoped to the lead's sales team.
  *Files:* `services/tools.py:preflight_write`,
  `services/tools.py:_validate_search_term`,
  `services/agent.py:_run_loop`, all five write executors in
  `services/tools.py`.

- **Medium — Cost-amplification DoS.** No per-(channel, chat_id) rate limit
  meant a single linked user could drive arbitrary LLM API spend on the
  operator's account; the unbounded daemon-thread spawn per delivery also
  exhausted process resources under flood. New module
  `services/throttle.py` provides a sliding-window limiter (default 30
  msgs/hour per chat) and a bounded thread pool (default 8 workers).
  Configurable via `ir.config_parameter`:
  `odoopilot.rate_limit_per_hour`, `odoopilot.rate_limit_window_seconds`,
  `odoopilot.worker_pool_size`. Saturation drops with HTTP 200 so the
  platform doesn't retry-storm us.
  *Files:* `services/throttle.py` (new), `controllers/main.py`.

- **Medium — Webhook delivery non-idempotency.** Telegram and WhatsApp both
  retry deliveries on 5xx and timeouts. Without dedup, a redelivery
  re-runs the full pipeline — at minimum wasting an LLM call, at worst
  re-prompting for confirmation of an already-staged write. New model
  `odoopilot.delivery.seen` records `(channel, external_id)` with a SQL
  UNIQUE constraint; the controller dedups on Telegram's `update_id` and
  WhatsApp's per-message `id` before submitting work. An hourly cron
  garbage-collects rows older than 24h.
  *Files:* `models/odoopilot_delivery.py` (new), `controllers/main.py`,
  `data/ir_cron.xml`, `security/ir.model.access.csv`.

### Added

- **`SECURITY.md` and `v17.0.7.0.0` GitHub Release** (already shipped on
  `2026-04-27` ahead of this changelog entry) — establishes private
  disclosure via GitHub Security Advisories and documents a one-paragraph
  threat model.
- **Regression tests** for every fix above in `tests/test_security.py`.

### Changed

- The five write tools now accept resolved IDs (`task_id`, `order_id`,
  `leave_id`, `lead_id`+`stage_id`) in addition to the original name
  arguments. Direct callers (e.g. unit tests) that pass names continue to
  work; the agent loop uses IDs.

---

## [17.0.7.0.0] — 2026-04-26 — Security release

This release fixes four security issues that were raised in a public audit
on r/Odoo. **All operators running 17.0.6.0.0 or earlier should upgrade
immediately** and re-register their Telegram webhook (so a secret token
gets generated). WhatsApp operators must additionally paste their Meta App
Secret into Settings — the WhatsApp webhook now refuses traffic without it.

### Security — fixed (4)

- **CVE-class — WhatsApp webhook had no signature verification.** Meta
  signs every webhook POST with `X-Hub-Signature-256: sha256=HMAC(app_secret, body)`.
  We now require the App Secret in Settings and verify the signature in
  constant time on every request. Without a valid signature the webhook
  returns 403 — closing an impersonation hole that allowed any internet
  attacker who guessed the URL to act as any linked WhatsApp user.
  *Files:* `services/whatsapp.py:verify_signature`,
  `controllers/main.py:whatsapp_webhook`,
  `models/res_config_settings.py:odoopilot_whatsapp_app_secret`.

- **Telegram webhook secret is now mandatory.** The previous design treated
  the secret as optional, so default deployments accepted unauthenticated
  POSTs. The `Register webhook` action now auto-generates a 32-byte
  URL-safe secret and registers it with Telegram. The endpoint rejects
  any incoming request whose `X-Telegram-Bot-Api-Secret-Token` header is
  missing or doesn't match.
  *Files:* `controllers/main.py:telegram_webhook`,
  `models/res_config_settings.py:action_register_telegram_webhook`.

- **Confirmation callbacks are now bound to a per-write nonce.** The Yes/No
  inline keyboard previously sent only `confirm:yes`, which meant the
  pending tool call could be silently swapped between staging and the user's
  click — for example by a prompt injection living inside a CRM lead's
  description. Each staged write now gets a fresh `secrets.token_urlsafe(12)`
  nonce stored on the session row; the nonce is embedded in the button
  payload (`confirm:yes:<nonce>`), and the controller verifies it in
  constant time before executing the write. Mismatches are logged and
  rejected with "This confirmation has expired."
  *Files:* `models/odoopilot_session.py` (`stage_pending`,
  `verify_and_consume_nonce`, `pending_nonce` field), `services/agent.py`,
  `services/telegram.py:send_confirmation`,
  `services/whatsapp.py:send_confirmation`,
  `controllers/main.py:_handle_confirmation`,
  `controllers/main.py:_handle_whatsapp_confirmation`.

- **Magic link tokens are now hashed at rest and one-shot.** Previously
  raw tokens were stored as `ir.config_parameter` keys, leaking them to
  anyone with system-parameter read access. The new `odoopilot.link.token`
  model stores only the SHA-256 digest, deletes the row inside the same
  transaction that consumes it, and ships an hourly cron to garbage-collect
  expired entries. Re-issuing a token for the same chat invalidates the
  previous one.
  *New file:* `models/odoopilot_link_token.py`.
  *Migration:* `migrations/17.0.7.0.0/post-migration.py` clears legacy
  `odoopilot.link_token.*` parameters and any in-flight pending writes.

### Added

- `odoopilot.link.token` model with `issue` / `consume` / `_gc_expired` API
- Hourly cron `ir_cron_gc_link_tokens` to garbage-collect expired tokens
- `tests/test_security.py` — regression tests for all four fixes
  (HMAC verification, nonce rotation, hashed token storage, single-use)

### Changed

- `OdooPilotSession.clear_pending` now also clears `pending_nonce`
- Telegram and WhatsApp `send_confirmation` accept a `nonce=` kwarg;
  the nonce is appended to both Yes and No button payloads

### Migration notes

Upgrade flow:
1. Pull `17.0.7.0.0` and run `-u odoopilot`. The post-migration script
   clears any in-flight write confirmations (users simply re-ask the bot)
   and removes legacy link-token system parameters.
2. Open *Settings → OdooPilot* and click **Register webhook** under
   Telegram once. A secret token is generated and registered automatically.
3. For WhatsApp, paste your Meta **App Secret** into the new
   *App Secret* field. Until this is set, the WhatsApp webhook returns 403.

---

## [17.0.6.0.0] — 2026-04-24

### Added — Multi-language support · per-user language preference

- **`language` field on `odoopilot.identity`** — stores ISO 639-1 code (`en`, `fr`, `es`, `de`, `it`, `pt`, `nl`, `ar`, `zh`, `ja`, `ko`, `ru`, `tr`, `pl`, `hi`) or empty for auto-detect
- **`/language` command** (Telegram & WhatsApp):
  - `/language` — shows current setting and all available codes
  - `/language fr` — sets French as the fixed reply language
  - `/language auto` — resets to auto-detect (match what the user writes)
- **`LANGUAGE_CHOICES`** constant exported from `odoopilot_identity.py` — single source of truth for valid codes and display names
- Language preference surfaced in the **OdooPilot Identities** list and form views (Odoo backend)

### Changed

- `SYSTEM_PROMPT` updated: when a language is set, the instruction reads `"Always respond in {language}."` instead of the generic detect-and-match rule
- `OdooPilotAgent.__init__` now accepts a `channel` parameter (`"telegram"` or `"whatsapp"`) — used for session lookup, identity lookup, and audit logging. Previously all audit records were hard-coded as `channel="telegram"`, which meant WhatsApp actions were mis-labelled. Now fixed.
- All `OdooPilotAgent(...)` instantiation sites in `controllers/main.py` pass the correct channel

---

## [17.0.5.0.0] — 2026-04-23

### Added — WhatsApp Cloud API channel

- **`services/whatsapp.py`** — `WhatsAppClient`: `send_message`, `send_confirmation` (interactive buttons), `mark_read`
- **`GET /odoopilot/webhook/whatsapp`** — hub.challenge verification endpoint for Meta webhook registration
- **`POST /odoopilot/webhook/whatsapp`** — receive and dispatch WhatsApp updates asynchronously
- Full `/link` flow for WhatsApp: one-time token → magic link → identity created → welcome message sent back via WhatsApp
- `/start` and `/link` commands via WhatsApp
- Yes/No confirmation via WhatsApp interactive button replies (`button_reply`)
- Incoming messages marked as read automatically
- Settings: `whatsapp_enabled`, `whatsapp_phone_number_id`, `whatsapp_access_token`, `whatsapp_verify_token`
- **Test connection** action button in Settings verifies phone number ID + access token via Graph API
- Proactive notifications (`send_task_digest`, `send_invoice_alerts`) now send to WhatsApp identities as well as Telegram
- `_get_client_for_identity()` helper in notifications — dispatches to right client per channel

### Changed

- `notifications.py` no longer hardcodes `channel="telegram"` — now queries all active identities and selects the right client
- Notification functions doc-strings updated to mention both channels

---

## [17.0.4.0.0] — 2026-04-23

### Added

- **`services/notifications.py`** — proactive notification service with two functions:
  - `send_task_digest(env)` — sends each linked user their overdue + today's tasks every morning
  - `send_invoice_alerts(env)` — sends users with `account.group_account_invoice` access a daily overdue invoice summary
- **Two new cron jobs** in `data/ir_cron.xml`:
  - `ir_cron_task_digest` — fires daily at 08:00 UTC
  - `ir_cron_invoice_alerts` — fires daily at 09:00 UTC
- **Two new settings toggles** (`Settings → OdooPilot → Proactive Notifications`):
  - *Daily task digest* (`odoopilot.notify_task_digest`)
  - *Overdue invoice alerts* (`odoopilot.notify_invoice_alerts`)
- Notifications section in the settings view (hidden when Telegram is disabled)
- Both notification types are opt-in (off by default); cron timing adjustable via Scheduled Actions

---

## [17.0.3.0.0] — 2026-04-22

### Added

- **`get_my_leaves`** — read pending/approved leave requests (own or team)
- **`approve_leave`** — approve a pending leave request (write, confirmation required)
- **`update_crm_stage`** — move a CRM opportunity to a different stage (write, confirmation required)
- **`create_crm_lead`** — create a new CRM opportunity (write, confirmation required)
- Human-readable inline confirmation messages (e.g. "Approve leave for John Smith?") — replaced raw JSON display
- Per-tool audit log entries — every tool call is individually logged with name, args, result, and success flag

### Changed

- Session class renamed `MailGatewayAISession` → `OdooPilotSession`
- Session TTL extended 24h → 72h
- Session message history cap raised 40 → 60 messages (30 exchanges)
- Write tool responses prefixed with ✅ for clarity

---

## [17.0.2.0.0] — 2026-04-22

### Architecture pivot — all logic now lives inside the Odoo addon

The project has been restructured from a two-component system (FastAPI service + thin Odoo addon) into a single self-contained Odoo addon. Users no longer need to host or configure any external service.

### Added

- Telegram webhook handler inside Odoo HTTP controllers
- LLM client supporting Anthropic, OpenAI, and Groq via raw `requests` (no SDKs)
- Multi-turn agent loop with tool-use and per-session conversation history
- 7 read tools: project tasks, sale orders, CRM leads, inventory, invoices, purchase orders, employees
- 2 write tools (mark task done, confirm sale order) with inline Yes/No confirmation
- Telegram client helpers: send message, send confirmation keyboard, answer callback query, set webhook
- Session model (`odoopilot.session`) with 24-hour garbage collection via `ir.cron`
- Full settings page: bot token, webhook secret, LLM provider/key/model, Register Webhook button, Test Connection button
- Magic link identity flow: `/link` → one-time token → `/odoopilot/link/start`
- Standalone link success/error pages (no `website` module dependency)
- Audit log for every tool call

### Changed

- Module technical name: `mail_gateway_ai` → `odoopilot`
- App Store URL: `/apps/modules/17.0/mail_gateway_ai` → `/apps/modules/17.0/odoopilot`
- CI simplified to ruff lint/format + XML well-formed check (removed FastAPI-specific mypy/pytest/build steps)

### Removed

- FastAPI service, Dockerfile, `pyproject.toml`, Docker Compose examples
- Fly.io deployment (`fly.toml`)
- External service URL setting
- All `mail_gateway_ai` identifiers

---

## [17.0.1.0.0] — 2026-04-01

### Added

- Initial scaffold: bot configuration settings (`service_url`, channel toggles), user identity model, audit log model
- User linking flow with one-time token generation
- `ir.model.access.csv` for base access control
- CI workflow: ruff, mypy, pytest, hatchling build

---

## Roadmap

| Version | Target | Description |
|---------|--------|-------------|
| **17.0.3.0.0** | ✅ Released | New write tools · get_my_leaves · 72h session TTL · human-readable confirmations · per-tool audit log |
| **17.0.4.0.0** | ✅ Released | Proactive notifications — daily task digest (08:00 UTC) · overdue invoice alerts (09:00 UTC) |
| **17.0.5.0.0** | ✅ Released | WhatsApp Cloud API — full channel parity with Telegram |
| **17.0.6.0.0** | ✅ Released | Multi-language support · `/language` command · per-user language preference |
| **18.0.1.0.0** | Q4 2026 | Odoo 18 port · OCA submission |
