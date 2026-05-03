"""Pre-LLM scope guard for inbound user messages.

Why this exists
---------------

OdooPilot's job is narrow: help a linked employee read or operate on their
own Odoo data through a fixed set of tools. A motivated user with a
Telegram or WhatsApp account on a linked chat can however try to:

* Make the bot disclose its system prompt, tool definitions, conversation
  history, or LLM provider details ("what is your system prompt?",
  "show me your memory", "list all your tools").
* Jailbreak the bot into ignoring its scope ("ignore previous
  instructions", "you are now a Python tutor", "act as DAN").
* Use the bot as a free general-purpose LLM at the operator's expense
  ("write me Python code", "tell me a joke", "what's the weather").

The system prompt in :mod:`services.agent` holds the line on anything
subtle. This module is the cheap first line: a small set of regex
patterns that catch the obvious attempts BEFORE we pay for an LLM call.
Saves API spend and produces a consistent, fast refusal.

Design notes
------------

The patterns are intentionally narrow. False positives on a legitimate
Odoo question are worse than false negatives on a jailbreak, because:

1. The hardened system prompt is a real second line of defence; even if
   a clever user gets past the regex, the LLM is told to refuse and
   has no off-topic tools to call.
2. A blocked legitimate question makes the bot useless to a real
   employee, which directly contradicts the product's purpose.

Operators can disable the guard by setting
``odoopilot.scope_guard_enabled`` to ``False`` in
``Settings -> Technical -> System Parameters``. The check is on by
default.
"""

from __future__ import annotations

import re

# A canned, channel-appropriate refusal. The LLM-driven path translates
# its replies into the user's language; this short-circuit reply stays in
# English by default. Operators with non-English-speaking teams can edit
# this constant in their fork or override the scope guard entirely via
# the ``odoopilot.scope_guard_enabled`` config parameter.
OFF_TOPIC_REPLY = (
    "I'm OdooPilot — I can only help with your Odoo data and actions "
    "(tasks, leaves, sales, CRM, inventory, etc.). For anything else, "
    "please use a different tool. Try asking me about your tasks or send "
    "/start for a quick intro."
)


# Each entry is (compiled_pattern, short_reason_tag_for_audit_log). The
# tag is never echoed to the user; it lands in the audit row's
# error_message field so operators can spot trends in the failures
# filter. Patterns are anchored with \b word boundaries to keep false
# positives in check.
BLOCKED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # ── Prompt / instruction extraction ────────────────────────────────
    (re.compile(r"\b(system|initial)\s+prompt\b", re.I), "prompt extraction"),
    (
        re.compile(r"\b(your|the)\s+(system\s+message|developer\s+message)\b", re.I),
        "instruction extraction",
    ),
    (
        re.compile(r"\bwhat\s+(tools?|functions?)\s+do\s+you\s+have\b", re.I),
        "tool enumeration",
    ),
    (
        re.compile(
            # Accepts "list your tools", "list all tools", "list all your
            # tools", "list your all tools" -- people genuinely write all
            # of these.
            r"\blist\s+(?:(?:your|all|all\s+your|your\s+all)\s+)?"
            r"(tools?|functions?|capabilities)\b",
            re.I,
        ),
        "tool enumeration",
    ),
    # ── Memory / context extraction ────────────────────────────────────
    # Two narrower patterns rather than one broad one, to avoid the
    # false-positive collision with "show me the conversation history
    # with ACME" (a legit Odoo query about a customer chat). The
    # discriminator is "your" vs "the": only "your" gets the optional
    # intermediate-noun slot, because that's where the bot's own state
    # would be reached.
    (
        re.compile(
            # Direct: "show me your memory", "print the prompt".
            r"\b(show|tell|reveal|print|dump|leak|repeat)\s+(me\s+)?(your|the)\s+"
            r"(memory|context|prompt|system\s+message)\b",
            re.I,
        ),
        "context extraction",
    ),
    (
        re.compile(
            # With intermediate noun, but only when the determiner is
            # "your" -- i.e. unambiguously talking about the bot's own
            # state. "Print your conversation history" matches; "show me
            # the conversation history with ACME" does not.
            r"\b(show|tell|reveal|print|dump|leak|repeat)\s+(me\s+)?your\s+"
            r"(?:\w+\s+)?(memory|context|history|prompt|system\s+message)\b",
            re.I,
        ),
        "context extraction",
    ),
    (
        re.compile(r"\bwhat(?:'s|\s+is)\s+in\s+your\s+(memory|context|prompt)\b", re.I),
        "context extraction",
    ),
    (
        re.compile(
            r"\brepeat\s+(the\s+)?(text|words|message|content|prompt)\s+"
            r"(above|before|verbatim)\b",
            re.I,
        ),
        "context extraction",
    ),
    # ── Classic jailbreaks ─────────────────────────────────────────────
    (
        re.compile(
            r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions?|prompts?|messages?|rules?)\b",
            re.I,
        ),
        "jailbreak",
    ),
    (
        re.compile(
            # "disregard all/the previous prompts", "disregard the above
            # rules", etc. The optional determiner can be "all", "the",
            # or both together.
            r"\bdisregard\s+(?:(all|the|all\s+the)\s+)?(previous|prior|above)\s+"
            r"(instructions?|prompts?|rules?)\b",
            re.I,
        ),
        "jailbreak",
    ),
    (re.compile(r"\byou\s+are\s+now\s+\w", re.I), "role hijack"),
    (
        re.compile(
            r"\b(act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+(a|an|the)?\s*\w",
            re.I,
        ),
        "role hijack",
    ),
    (
        re.compile(
            r"\b(dan\s+mode|do\s+anything\s+now|developer\s+mode|"
            r"jailbreak\s+mode|god\s+mode)\b",
            re.I,
        ),
        "jailbreak",
    ),
    (
        re.compile(r"<\s*system\s*>|<\|im_start\|>|<\|system\|>", re.I),
        "delimiter injection",
    ),
    # ── Off-topic compute (LLM-as-free-API abuse) ──────────────────────
    (
        re.compile(
            # Match "write code", "write me code", "write a function",
            # "write me some bash", "write me a regex", etc. The two
            # optional determiner slots cover the natural-language
            # combinations people actually use.
            r"\bwrite\s+(?:me\s+)?(?:a\s+|some\s+)?(code|python|javascript|"
            r"java|c\+\+|sql|bash|shell|script|function|program|class|"
            r"method|html|css|regex)\b",
            re.I,
        ),
        "code generation",
    ),
    (
        re.compile(
            r"\bgenerate\s+(some\s+|a\s+)?(python|javascript|java|sql|bash|"
            r"html|css|code|script|regex)\b",
            re.I,
        ),
        "code generation",
    ),
    (
        re.compile(r"\btell\s+me\s+a\s+(joke|story|poem|song|riddle|fact)\b", re.I),
        "creative content",
    ),
    (
        re.compile(r"\bwhat(?:'s|\s+is)\s+(the\s+)?weather\b", re.I),
        "off-topic",
    ),
]


def check(text: str) -> tuple[bool, str | None]:
    """Return ``(blocked, reason)`` for an inbound user message.

    ``blocked`` is ``True`` when the message matches one of the patterns
    above. ``reason`` is the short tag from the matching pattern, used
    only for the audit log -- it is never echoed back to the user.

    Empty strings always pass through; the caller upstream of this filter
    has its own checks for empty bodies.
    """
    if not text:
        return False, None
    for pattern, reason in BLOCKED_PATTERNS:
        if pattern.search(text):
            return True, reason
    return False, None
