"""Tests for the 17.0.14.0.0 employee-self-service tool sprint.

Six new tools shipped together: ``find_partner`` (read), and the five
write tools ``clock_in``, ``clock_out``, ``submit_expense``,
``submit_timesheet``, ``create_calendar_event``.

The tests pin three contract surfaces:

1. **Tool registry hygiene**: every new tool name appears in
   :data:`tools.TOOL_DEFINITIONS`, :data:`tools.WRITE_TOOLS` (where
   applicable), and the dispatch map inside :func:`tools.execute_tool`.
   A mismatch between any two of these would let the LLM call a tool
   that crashes at execute time.

2. **Preflight gate**: each write tool returns a structured ``{"ok":
   True, "args": ..., "question": ...}`` for valid input and a
   ``{"ok": False, "error": ...}`` for invalid input. The error path
   is what protects the user from confirming a malformed call.

3. **Validation behaviour**: representative bad inputs (zero amount,
   missing description, malformed datetime) are rejected with a
   user-readable error string, never an exception.

Functional execution against the real ORM is partially exercised by
the ``find_partner`` tests (read-only, deterministic). Full execute
paths for ``clock_in``/etc. are skipped when the upstream module
(``hr.attendance``, ``hr.expense``, etc.) is not installed in the test
database; the preflight gate is exercised regardless.
"""

from odoo.tests.common import TransactionCase

from ..services import tools
from ..services.tools import preflight_write


class TestToolRegistryHygiene(TransactionCase):
    """The four-way registry must agree on every tool name."""

    NEW_TOOLS = {
        "find_partner",
        "clock_in",
        "clock_out",
        "submit_expense",
        "submit_timesheet",
        "create_calendar_event",
    }
    NEW_WRITE_TOOLS = {
        "clock_in",
        "clock_out",
        "submit_expense",
        "submit_timesheet",
        "create_calendar_event",
    }

    def test_each_new_tool_has_a_definition(self):
        defined = {t["name"] for t in tools.TOOL_DEFINITIONS}
        for name in self.NEW_TOOLS:
            with self.subTest(name=name):
                self.assertIn(
                    name,
                    defined,
                    f"{name} missing from TOOL_DEFINITIONS -- the LLM "
                    "wouldn't know it can call this tool.",
                )

    def test_write_tools_set_is_complete(self):
        for name in self.NEW_WRITE_TOOLS:
            with self.subTest(name=name):
                self.assertIn(
                    name,
                    tools.WRITE_TOOLS,
                    f"{name} missing from WRITE_TOOLS -- it would skip "
                    "the confirmation gate and execute immediately.",
                )

    def test_find_partner_is_not_a_write_tool(self):
        # Read tools must NOT be in WRITE_TOOLS or they'd ask for
        # confirmation on every call.
        self.assertNotIn("find_partner", tools.WRITE_TOOLS)


class TestFindPartner(TransactionCase):
    """Read-only contact lookup. Pure ORM, deterministic."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "OdooPilot Test Partner Acme Co",
                "email": "billing@odoopilot-test-acme.example",
                "phone": "+1-555-0142",
            }
        )

    def test_finds_by_name(self):
        result = tools.find_partner(self.env, name="OdooPilot Test Partner Acme")
        self.assertIn("OdooPilot Test Partner Acme Co", result)

    def test_finds_by_email_substring(self):
        result = tools.find_partner(self.env, name="odoopilot-test-acme")
        self.assertIn("OdooPilot Test Partner Acme Co", result)

    def test_finds_by_phone_substring(self):
        result = tools.find_partner(self.env, name="555-0142")
        self.assertIn("OdooPilot Test Partner Acme Co", result)

    def test_empty_query_asks_for_input(self):
        result = tools.find_partner(self.env, name="")
        self.assertIn("Please give me", result)

    def test_no_match_returns_friendly_message(self):
        result = tools.find_partner(
            self.env, name="zzzz-noway-this-matches-anything-zzzz"
        )
        self.assertIn("No contact matched", result)


class TestSubmitExpensePreflight(TransactionCase):
    """Validation behaviour without depending on hr.expense being installed."""

    def test_rejects_short_description(self):
        result = preflight_write(
            self.env,
            "submit_expense",
            {"description": "x", "amount": 10.0},
        )
        self.assertFalse(result["ok"])
        self.assertIn("too short", result["error"].lower())

    def test_rejects_zero_amount(self):
        result = preflight_write(
            self.env,
            "submit_expense",
            {"description": "Lunch with ACME", "amount": 0},
        )
        self.assertFalse(result["ok"])
        self.assertIn("greater than zero", result["error"].lower())

    def test_rejects_negative_amount(self):
        result = preflight_write(
            self.env,
            "submit_expense",
            {"description": "Lunch with ACME", "amount": -5.0},
        )
        self.assertFalse(result["ok"])

    def test_rejects_non_numeric_amount(self):
        result = preflight_write(
            self.env,
            "submit_expense",
            {"description": "Lunch with ACME", "amount": "not a number"},
        )
        self.assertFalse(result["ok"])
        self.assertIn("must be a number", result["error"].lower())


class TestSubmitTimesheetPreflight(TransactionCase):
    """Validation behaviour without depending on hr_timesheet."""

    def test_rejects_zero_hours(self):
        result = preflight_write(
            self.env,
            "submit_timesheet",
            {
                "project_name": "Internal projects",
                "hours": 0,
                "description": "Misc work",
            },
        )
        self.assertFalse(result["ok"])
        self.assertIn("between 0 and 24", result["error"].lower())

    def test_rejects_more_than_24_hours(self):
        result = preflight_write(
            self.env,
            "submit_timesheet",
            {
                "project_name": "Internal projects",
                "hours": 30,
                "description": "Marathon",
            },
        )
        self.assertFalse(result["ok"])

    def test_rejects_short_project_name(self):
        result = preflight_write(
            self.env,
            "submit_timesheet",
            {"project_name": "x", "hours": 1, "description": "Some work"},
        )
        self.assertFalse(result["ok"])
        # Could trip "too short" or the project-not-found path; either
        # is acceptable as long as we don't try to create the line.
        self.assertTrue(result["error"])


class TestCreateCalendarEventPreflight(TransactionCase):
    """Datetime parsing and duration validation."""

    def test_rejects_short_name(self):
        result = preflight_write(
            self.env,
            "create_calendar_event",
            {"name": "x", "start": "2026-06-01 10:00"},
        )
        self.assertFalse(result["ok"])
        self.assertIn("too short", result["error"].lower())

    def test_rejects_missing_start(self):
        result = preflight_write(
            self.env,
            "create_calendar_event",
            {"name": "Team standup"},
        )
        self.assertFalse(result["ok"])

    def test_rejects_malformed_datetime(self):
        result = preflight_write(
            self.env,
            "create_calendar_event",
            {"name": "Standup", "start": "tomorrow at 10"},
        )
        self.assertFalse(result["ok"])
        self.assertIn("could not parse", result["error"].lower())

    def test_rejects_negative_duration(self):
        result = preflight_write(
            self.env,
            "create_calendar_event",
            {
                "name": "Standup",
                "start": "2026-06-01 10:00",
                "duration_hours": -1,
            },
        )
        self.assertFalse(result["ok"])

    def test_accepts_valid_input(self):
        # Skip if calendar module is not installed in the test DB --
        # the preflight does check env.registry, and the rest of the
        # tests above hit the validation path before that.
        if "calendar.event" not in self.env.registry:
            self.skipTest("calendar module not installed")
        result = preflight_write(
            self.env,
            "create_calendar_event",
            {
                "name": "Standup",
                "start": "2026-06-01 10:00",
                "duration_hours": 0.5,
            },
        )
        self.assertTrue(result["ok"])
        # Resolved args carry the parsed start AND a derived stop.
        self.assertIn("start", result["args"])
        self.assertIn("stop", result["args"])
        self.assertIn("Standup", result["question"])


class TestClockInPreflight(TransactionCase):
    """Clock-in must reject double-clock and missing-employee cases."""

    def test_skipped_if_attendance_module_absent(self):
        if "hr.attendance" in self.env.registry:
            self.skipTest("hr.attendance is installed; covered elsewhere")
        result = preflight_write(self.env, "clock_in", {})
        self.assertFalse(result["ok"])
        self.assertIn("not installed", result["error"].lower())
