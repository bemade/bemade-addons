"""UC-CAT-01 — Manage domains.

AC1: domain has code (unique), name, sequence; archivable.
AC2: competencies group and sort by domain.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatDomain(CbetCommon):
    def test_domain_fields_and_archive(self):
        d = self.env["cbet.domain"].create(
            {"code": "PRE", "name": "Prétraitement", "sequence": 5})
        self.assertTrue(d.active)
        d.active = False
        self.assertFalse(d.active)

    @mute_logger("odoo.sql_db")
    def test_domain_code_unique(self):
        with self.assertRaises(Exception):
            self.env["cbet.domain"].create({"code": "TST", "name": "dup"})

    def test_competency_count_and_grouping(self):
        self._make_competency("TST-01")
        self._make_competency("TST-02")
        self.assertEqual(self.domain.competency_count, 2)
