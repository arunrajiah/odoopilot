## Configuration

Go to **Settings → OdooPilot** (requires System Administrator access).

### Telegram

| Setting | Description |
|---------|-------------|
| Enable OdooPilot | Master toggle — enables the Telegram webhook |
| Bot Token | The token from @BotFather (e.g. `123456:ABC-DEF...`) |
| Webhook Secret | A random secret string used to validate incoming Telegram requests |

After filling in the token and secret, click **Register Webhook** to call Telegram's `setWebhook` API automatically. You can also click **Test Connection** to verify the token is valid (calls `getMe`).

### LLM Provider

| Setting | Description |
|---------|-------------|
| Provider | `Anthropic`, `OpenAI`, or `Groq` |
| API Key | Your key from the chosen provider |
| Model | The model name, e.g. `claude-opus-4-5`, `gpt-4o`, `llama3-70b-8192` |

The API key is stored encrypted and never shown again after saving.

### Linking employees

Once the bot is configured, employees link their Telegram account to their Odoo user by:

1. Sending `/link` to the Telegram bot
2. Clicking the magic link returned by the bot (must be logged into Odoo)
3. The link expires after 10 minutes and is single-use

Linked accounts are visible under **OdooPilot → Identities**.

### Audit log

Every AI action (tool call) is logged under **OdooPilot → Audit Log** with:
- Timestamp
- Odoo user
- Tool name
- Input arguments
- Success / error result
