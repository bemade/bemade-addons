"""UC-CAT-02 — Create competency.

AC1: code XXX-NN unique (case-insensitive); constraint violation raises.
AC2: kind ∈ {procedural, theoretical, orchestration}.
AC4: new competency starts in draft, version 0.x.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatCompetency(CbetCommon):
    def test_defaults_draft_and_version(self):
        c = self._make_competency("TST-10")
        self.assertEqual(c.state, "draft")
        self.assertTrue(c.version.startswith("0."))
        self.assertEqual(c.kind, "procedural")

    def test_code_format_enforced(self):
        with self.assertRaises(ValidationError):
            self._make_competency("BADCODE")

    def test_code_case_insensitive_unique(self):
        self._make_competency("TST-20")
        with self.assertRaises(ValidationError):
            self._make_competency("tst-20")

    def test_default_unit_autocreated(self):
        # UC-CAT-06 AC1 — a default unit exists on create.
        c = self._make_competency("TST-30")
        self.assertEqual(len(c.unit_ids), 1)
        self.assertTrue(c.unit_ids.is_default)
