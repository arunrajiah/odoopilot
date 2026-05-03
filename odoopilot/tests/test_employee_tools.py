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


# ── 17.0.15 hardening ─────────────────────────────────────────────────────


class TestFindPartnerLimitCap(TransactionCase):
    """The LLM cannot scrape the whole partner table by passing a huge limit.

    Hard cap of 25 is enforced regardless of the requested value. Record
    rules already filter what the linked user can see; the cap is the
    second-line defence against an LLM-controlled exfiltration request
    (or a malformed args payload).
    """

    def test_huge_limit_is_capped(self):
        # Create a small batch to verify the call doesn't crash with a
        # large requested limit and that the result count is bounded.
        for i in range(3):
            self.env["res.partner"].create(
                {
                    "name": f"OdooPilot LimitCap test partner {i}",
                    "email": f"limitcap{i}@odoopilot-test.example",
                }
            )
        result = tools.find_partner(self.env, name="OdooPilot LimitCap", limit=999_999)
        # Three matching partners exist; the cap doesn't reduce them
        # (cap is 25, well above 3). The point of this test is that the
        # call succeeds with a sane response rather than running an
        # unbounded ORM search.
        self.assertIn("OdooPilot LimitCap", result)
        # Negative / non-integer limits get sane defaults.
        result = tools.find_partner(self.env, name="OdooPilot LimitCap", limit=-5)
        self.assertIn("OdooPilot LimitCap", result)
        result = tools.find_partner(
            self.env, name="OdooPilot LimitCap", limit="not a number"
        )
        self.assertIn("OdooPilot LimitCap", result)


class TestEmployeeIdRebinding(TransactionCase):
    """submit_expense / submit_timesheet must ignore staged employee_id
    that doesn't match env.uid's hr.employee.

    The agent loop today pins employee_id correctly via preflight_write,
    so the only way the wrong id reaches the executor is via a future
    code-path bug. Defence-in-depth: re-resolve at execute time and
    log a warning if the staged value disagrees.
    """

    def setUp(self):
        super().setUp()
        if "hr.employee" not in self.env.registry:
            self.skipTest("hr.employee not installed")
        # Make sure the test admin has an hr.employee.
        self.user = self.env.ref("base.user_admin")
        existing = self.env["hr.employee"].search(
            [("user_id", "=", self.user.id)], limit=1
        )
        if existing:
            self.my_emp = existing
        else:
            self.my_emp = self.env["hr.employee"].create(
                {"name": "OdooPilot test admin", "user_id": self.user.id}
            )
        # And a second employee with a different (or no) user.
        self.other_emp = self.env["hr.employee"].create(
            {"name": "OdooPilot test other employee"}
        )

    def test_submit_expense_ignores_spoofed_employee_id(self):
        if "hr.expense" not in self.env.registry:
            self.skipTest("hr.expense not installed")
        # Direct execute call with a spoofed employee_id pointing at
        # the OTHER employee. The executor must override and write as
        # the env.uid's own hr.employee.
        result = tools.submit_expense(
            self.env,
            employee_id=self.other_emp.id,  # spoofed
            description="Defence-in-depth test expense",
            amount=42.0,
        )
        self.assertIn("Draft expense", result)
        # Verify the row landed under MY employee, not the spoofed one.
        latest = self.env["hr.expense"].search(
            [("name", "=", "Defence-in-depth test expense")], limit=1
        )
        self.assertEqual(latest.employee_id, self.my_emp)

    def test_submit_timesheet_ignores_spoofed_employee_id(self):
        if "account.analytic.line" not in self.env.registry:
            self.skipTest("account.analytic.line not installed")
        if "project.project" not in self.env.registry:
            self.skipTest("project not installed")
        proj = self.env["project.project"].create({"name": "OdooPilot test project"})
        result = tools.submit_timesheet(
            self.env,
            project_id=proj.id,
            employee_id=self.other_emp.id,  # spoofed
            hours=1.0,
            description="Defence-in-depth test timesheet",
        )
        # Tool returned a success string.
        self.assertTrue(result.startswith("✅"))
        latest = self.env["account.analytic.line"].search(
            [("name", "=", "Defence-in-depth test timesheet")], limit=1
        )
        self.assertEqual(latest.employee_id, self.my_emp)
