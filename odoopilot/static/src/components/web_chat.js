/** @odoo-module **/
/*
 * OdooPilot in-Odoo web chat widget.
 *
 * Renders a chatbot icon in Odoo's systray (top-right of the
 * navigation bar). Click the icon -> a panel slides down with the
 * conversation history and an input field. Submit -> POSTs to
 * /odoopilot/web/message and renders the buffered reply envelopes.
 *
 * Compatibility: written against the OWL 2 / OWL 3 common subset so
 * the same source ships on both the 17.0 and 18.0 branches without
 * conditional imports.
 *
 * Trust model: the widget never receives the user's API keys, bot
 * tokens, or webhook secrets -- those stay server-side. Messages are
 * rendered as plain text (t-esc, never t-raw) so a malicious tool
 * result cannot inject HTML into the page.
 */

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class OdooPilotWebChat extends Component {
    static template = "odoopilot.WebChat";
    static props = {};

    setup() {
        this.state = useState({
            // Did /config say the operator enabled the widget?
            enabled: false,
            configLoaded: false,
            // Is the panel currently expanded?
            open: false,
            // Conversation history. Each entry:
            //   {role: "user"|"assistant", type: "text"|"confirm",
            //    text?: string, question?: string, nonce?: string}
            messages: [],
            // The current user-input text.
            input: "",
            // True while a /message request is in flight; gates the
            // submit button + Enter key + confirmation buttons so a
            // double-click can't fire two LLM calls in parallel.
            sending: false,
        });
        this.scrollRef = useRef("scroll");
        onMounted(() => this._loadConfig());
    }

    /**
     * Ask the server whether the widget should render at all. If the
     * operator has the master flag off, we never show the icon. We
     * still load the JS into the asset bundle (cheap) but the
     * component renders nothing.
     */
    async _loadConfig() {
        try {
            const cfg = await rpc("/odoopilot/web/config", {});
            this.state.enabled = !!(cfg && cfg.enabled);
        } catch (e) {
            // Network or server error: treat as "off" rather than
            // showing a broken widget. The operator gets the error
            // in the server log; the user gets a clean Odoo UI.
            this.state.enabled = false;
        } finally {
            this.state.configLoaded = true;
        }
    }

    /**
     * Toggle the panel open/closed. On open, focus the input.
     */
    _toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            // Defer until the panel is in the DOM.
            setTimeout(() => {
                const el = document.getElementById("odoopilot-web-chat-input");
                if (el) {
                    el.focus();
                }
                this._scrollToBottom();
            }, 0);
        }
    }

    _onKeydown(ev) {
        // Plain Enter sends; Shift+Enter inserts a newline. Matches
        // every other chat app on earth.
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this._send();
        }
    }

    /**
     * Send the current input field to the server. Pure user action;
     * confirmation clicks go through ``_confirm`` instead.
     */
    async _send() {
        const text = (this.state.input || "").trim();
        if (!text || this.state.sending) {
            return;
        }
        this.state.input = "";
        this.state.messages.push({ role: "user", type: "text", text });
        this._scrollToBottom();
        await this._post(text);
    }

    /**
     * Click handler for the Yes / No buttons rendered on a
     * confirmation envelope. ``answer`` is "yes" or "no".
     */
    async _confirm(nonce, answer) {
        if (this.state.sending || !nonce) {
            return;
        }
        // Show the user's choice as a chat bubble for clarity.
        this.state.messages.push({
            role: "user",
            type: "text",
            text: answer === "yes" ? "Yes, do it." : "No, cancel.",
        });
        this._scrollToBottom();
        await this._post(`confirm:${answer}:${nonce}`);
    }

    /**
     * Common POST + envelope-rendering path. Used by both _send and
     * _confirm. Catches network errors and surfaces them as a chat
     * bubble rather than an unhandled rejection.
     */
    async _post(message) {
        this.state.sending = true;
        try {
            const resp = await rpc("/odoopilot/web/message", { message });
            const items = (resp && resp.items) || [];
            for (const item of items) {
                this.state.messages.push({
                    role: "assistant",
                    type: item.type,
                    text: item.text || "",
                    question: item.question || "",
                    nonce: item.nonce || "",
                });
            }
            if (resp && resp.error === "disabled") {
                // Operator disabled the widget mid-session. Stop
                // rendering on the next config check.
                this.state.enabled = false;
            }
        } catch (e) {
            this.state.messages.push({
                role: "assistant",
                type: "text",
                text:
                    "Sorry, I couldn't reach OdooPilot just now. " +
                    "Please try again or use the Telegram / WhatsApp channel.",
            });
        } finally {
            this.state.sending = false;
            this._scrollToBottom();
        }
    }

    _scrollToBottom() {
        // Defer one tick so the new bubble is in the DOM before we
        // measure the scroll height.
        setTimeout(() => {
            if (this.scrollRef.el) {
                this.scrollRef.el.scrollTop = this.scrollRef.el.scrollHeight;
            }
        }, 0);
    }
}

// Register in the systray. The sequence places us to the left of
// Odoo's own systray entries (user menu, switch-company, etc.).
registry.category("systray").add("odoopilot.WebChat", {
    Component: OdooPilotWebChat,
    sequence: 100,
});
