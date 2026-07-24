"""UC-RPT-04 — Training matrix (cbet.employee.competency.status SQL view).

AC1: per-(employee, competency) state incl. non-certified 'none' cells.
AC3: backed by a SQL view.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestRptMatrix(CbetCommon):
    def _status(self, emp, comp):
        rec = self.env["cbet.employee.competency.status"].search([
            ("employee_id", "=", emp.id), ("competency_id", "=", comp.id)])
        return rec.state

    def test_matrix_states(self):
        valid_comp = self._make_competency("RPT-10")
        expired_comp = self._make_competency("RPT-11")
        none_comp = self._make_competency("RPT-12")
        emp = self._make_employee("Cand M")

        self._certify(emp, valid_comp, valid_to=Date.today() + relativedelta(years=1))
        # Well clear of the CURRENT_DATE boundary (the view uses the PG server
        # date, which can differ from Odoo's UTC 'today' by a day).
        self._certify(emp, expired_comp, valid_to=Date.today() - relativedelta(days=30))
        # none_comp: a training line but no certification → 'none' cell.
        self.env["cbet.training.line"].create(
            {"employee_id": emp.id, "competency_id": none_comp.id})

        self.assertEqual(self._status(emp, valid_comp), "valid")
        self.assertEqual(self._status(emp, expired_comp), "expired")
        self.assertEqual(self._status(emp, none_comp), "none")
