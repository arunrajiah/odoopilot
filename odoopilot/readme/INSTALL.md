## Installation

### Prerequisites

- A running [OdooPilot](https://github.com/arunrajiah/odoopilot) service (see its README for setup).
- Odoo 17.0 or 18.0 Community edition.

### Steps

1. Copy the `odoopilot` directory into your Odoo addons path.
2. Restart Odoo and update the addon list (`-u all` or via Settings → Update Apps List).
3. Install **AI Mail Gateway** from Apps.
4. Go to **Settings → OdooPilot** and enter the URL of your running OdooPilot service.
5. Enable the channels you want (Telegram, and later WhatsApp).

### User linking

Each employee who wants to use the bot must link their account:

1. In Odoo, open their user profile or the OdooPilot linking page.
2. Click **Link Telegram Account** — this generates a one-time link.
3. Click the link while logged into Odoo.
4. Send `/start` to the Telegram bot — they are now linked.
