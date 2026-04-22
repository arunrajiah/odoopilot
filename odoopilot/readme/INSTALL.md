## Installation

### Prerequisites

- Odoo **17.0 Community** (self-hosted or Odoo.sh)
- Odoo must be reachable from the internet so Telegram can deliver webhook events
- A Telegram Bot token — create one via [@BotFather](https://t.me/BotFather)
- An API key from [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), or [Groq](https://console.groq.com)

No extra Python packages are required. OdooPilot uses only `requests` (already available in Odoo's environment) for external API calls.

### From the Odoo App Store

1. Open **Apps** in your Odoo instance and search for **OdooPilot**.
2. Click **Install**.
3. Go to **Settings → OdooPilot** and follow the [Configuration guide](CONFIGURE.md).

### Manual installation

1. Copy the `odoopilot/` directory into your Odoo addons path.
2. Restart Odoo.
3. Go to **Settings → Apps**, click **Update Apps List**, then search for **OdooPilot** and install it.

```bash
# Or install directly via CLI
./odoo-bin -c odoo.conf -i odoopilot
```

### Odoo.sh

Upload the `odoopilot/` folder to your repository's addons path and push. Odoo.sh will pick it up on the next build.

### Upgrading

```bash
./odoo-bin -c odoo.conf -u odoopilot
```

No manual database migrations are needed — Odoo handles schema updates automatically on upgrade.

### Uninstalling

Uninstall via **Settings → Apps**. All OdooPilot data (identities, sessions, audit log) will be removed along with the addon.
