# AI Mail Gateway

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![OCA/social](https://img.shields.io/badge/GitHub-OCA%2Fsocial-lightgrey.svg?logo=github)](https://github.com/OCA/social)

**Companion Odoo addon for [OdooPilot](https://github.com/arunrajiah/odoopilot)** — the open-source AI messaging bridge for Odoo Community.

This module provides the Odoo-side UI for bot configuration, user account linking, and audit log viewing. The AI logic lives in the standalone OdooPilot Python service.

<!-- /!\ do not modify above this line -->

## Description

**AI Mail Gateway** bridges Odoo Community with external messaging apps (Telegram first, WhatsApp in v0.3) via an AI agent.

### Features

- **User linking** — Generate one-time tokens so employees can link their Telegram account to their Odoo identity.
- **Bot configuration** — Set the OdooPilot service URL and enable/disable channels from Odoo Settings.
- **Audit log viewer** — See every tool call made on behalf of each user, with timestamps and results.

## Installation

1. Copy `mail_gateway_ai` into your Odoo addons path.
2. Update the addon list and install **AI Mail Gateway**.
3. Go to **Settings → OdooPilot** and enter your OdooPilot service URL.

See [INSTALL.md](readme/INSTALL.md) for full instructions.

## Configuration

Go to **Settings → Technical → OdooPilot**. See [CONFIGURE.md](readme/CONFIGURE.md).

## Bug Tracker

Bugs are reported at <https://github.com/arunrajiah/odoopilot/issues>.

## Credits

### Authors

- OdooPilot Contributors

### Contributors

See [CONTRIBUTORS.md](readme/CONTRIBUTORS.md).

## License

This module is licensed under the [LGPL-3 or later](https://www.gnu.org/licenses/lgpl-3.0.en.html).
