# Security Policy

OdooPilot is an Odoo addon that connects external messaging platforms
(Telegram, WhatsApp) to your Odoo instance and lets an LLM read and write
Odoo records on your behalf. Because every install touches business data,
we treat security as a first-class part of the project, not an afterthought.

## Supported versions

We patch security issues on the latest minor release of every Odoo major
version we still support. Older patch versions on the same minor line
should upgrade to the latest patch on that line.

| Odoo series | Branch | Status            |
|-------------|--------|-------------------|
| 18.0        | `18.0` | Alpha (preview)   |
| 17.0        | `17.0` | Supported         |
| 16.0        | `16.0` | Not yet released  |
| < 16.0      | n/a    | Not supported     |

The `main` branch tracks the latest supported series and is where security
fixes land first before being mirrored to the per-version branches the
Odoo App Store reads from.

## Reporting a vulnerability

**Please do not file a public GitHub issue, post on Reddit, or otherwise
disclose a suspected vulnerability publicly before we have had a chance
to fix it.** Affected operators may be running production Odoo instances
with real customer data; coordinated disclosure protects them.

The preferred channel is **GitHub Security Advisories**:

1. Go to [github.com/arunrajiah/odoopilot/security/advisories/new](https://github.com/arunrajiah/odoopilot/security/advisories/new)
2. Fill in the form. Include a proof of concept if you have one, the
   commit hash you tested against, and your suggested severity.
3. We will acknowledge within **72 hours** and aim to ship a patched
   release within **14 days** for High/Critical issues. Lower-severity
   issues may take longer; we will keep you updated in the advisory
   thread.

If GitHub Security Advisories are not available to you, email
`arunrajiah@gmail.com` with the subject line `OdooPilot security
report` and the same information.

You may request credit in the published advisory and the changelog;
this is the default unless you ask to remain anonymous.

## What is in scope

Vulnerabilities in any of the following are in scope:

- The Odoo addon code under `odoopilot/` on a supported branch
- Webhook endpoints registered by the addon
  (`/odoopilot/webhook/telegram`, `/odoopilot/webhook/whatsapp`,
  `/odoopilot/link/*`)
- The LLM tool layer in `odoopilot/services/tools.py` and the agent
  loop in `odoopilot/services/agent.py` — including reasonable
  prompt-injection scenarios that escalate beyond the linked user's
  Odoo record-rule permissions
- Privilege escalation between linked messaging users
- Secret leakage (LLM API keys, webhook secrets, magic-link tokens)
  via logs, audit records, error replies, or stored fields

## What is out of scope

- Vulnerabilities in Odoo itself — please report those upstream to
  Odoo SA
- Vulnerabilities in third-party LLM providers (Anthropic, OpenAI,
  Groq, Meta WhatsApp Cloud API, Telegram Bot API)
- Findings that require an attacker to already have full administrator
  access to the Odoo instance
- Social-engineering attacks against operators or end-users
- Denial-of-service via paid LLM cost amplification when the operator
  has not configured per-user rate limits — we document this risk
  and provide knobs, but no addon can prevent an authenticated linked
  user from sending expensive prompts

## Threat model in one paragraph

The trust boundary is: **untrusted = anything the LLM sees**. That
includes inbound chat messages, the body of any Odoo record the LLM is
allowed to read (lead descriptions, sale order notes, customer names,
audit-log entries), and any media the bot downloads. Trusted = the
addon's own configuration written by an Odoo administrator, the
constants in the codebase, and the LLM's tool definitions. Every
write action must be confirmed by the linked user with a
single-use nonce; reads run as the linked user with full record-rule
enforcement; webhooks are HMAC-verified before any business logic runs.
A successful prompt injection should at worst be able to do what the
linked user could already do interactively, never more.

## Hall of fame

Researchers who have responsibly disclosed an issue:

- **u/jeconti** (Reddit) — public audit, 2026-04-25 — four issues
  fixed in [v17.0.7.0.0](CHANGELOG.md#1707---20260426---security-release).
  Disclosure was public; we have asked future reports to use the
  private channel above.

If you'd like to be listed here, mention it in your advisory.
