"""UC-RPT-04 — Training matrix (cbet.employee.competency.status SQL view).

AC1: per-(employee, competency) state incl. non-certified 'none' cells.
AC2: the matrix covers what an employee is *required* to hold — the closure of
     the standards they are qualifying against — so gaps are visible, not just
     holdings; each cell says whether it is required.
AC3: backed by a SQL view.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestRptMatrix(CbetCommon):
    def _cell(self, emp, comp):
        return self.env["cbet.employee.competency.status"].search([
            ("employee_id", "=", emp.id), ("competency_id", "=", comp.id)])

    def _status(self, emp, comp):
        return self._cell(emp, comp).state

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

    def test_requirements_surface_as_gaps(self):
        # AC2 — the whole point of a training matrix is the empty cells. A
        # competency the employee's standard requires, but which they have
        # never been certified on and have no training line for, must appear.
        held = self._make_competency("RPT-20")
        gap = self._make_competency("RPT-21")
        deep = self._make_competency("RPT-22")
        # gap requires deep, so deep enters the standard's closure too.
        self.env["cbet.prerequisite"].create({
            "competency_id": gap.id, "prerequisite_id": deep.id,
            "prereq_type": "obligatoire"})
        emp = self._make_employee("Cand Gap")
        std = self._make_standard("Gap standard", essentials=[held, gap])
        self.env["cbet.qualification"]._get_or_create(emp, std)
        self._certify(emp, held, valid_to=Date.today() + relativedelta(years=1))

        self.assertEqual(self._status(emp, held), "valid")
        self.assertEqual(self._status(emp, gap), "none")     # declared, missing
        self.assertEqual(self._status(emp, deep), "none")    # pulled in, missing

    def test_required_flag_distinguishes_extras(self):
        # A cell says whether the standard actually asks for it, so "gaps only"
        # is a filter rather than a spreadsheet exercise.
        required = self._make_competency("RPT-23")
        extra = self._make_competency("RPT-24")
        emp = self._make_employee("Cand Extra")
        std = self._make_standard("Flag standard", essentials=[required])
        self.env["cbet.qualification"]._get_or_create(emp, std)
        # Certified on something the standard never asked for.
        self._certify(emp, extra, valid_to=Date.today() + relativedelta(years=1))

        self.assertTrue(self._cell(emp, required).is_required)
        self.assertFalse(self._cell(emp, extra).is_required)
        self.assertEqual(self._status(emp, extra), "valid")

    def test_no_qualification_means_no_requirement_rows(self):
        # An employee who is not qualifying against any standard does not get a
        # row per catalogue competency — only what they actually hold.
        comp = self._make_competency("RPT-25")
        other = self._make_competency("RPT-26")
        emp = self._make_employee("Cand Loose")
        self._make_standard("Unrelated standard", essentials=[other])
        self._certify(emp, comp, valid_to=Date.today() + relativedelta(years=1))

        self.assertEqual(self._status(emp, comp), "valid")
        self.assertFalse(self._cell(emp, other))

    def test_cell_id_keeps_denoting_the_same_cell(self):
        """A cell's id must identify its (employee, competency), not its position.

        The ORM reads a record in two steps — ``search`` returns ids, the
        following ``read`` matches on ``id IN (...)`` and never re-checks
        employee or competency. It also caches by id, and in ``TransactionCase``
        that cache survives the rollback between test methods. So an id that
        stops meaning the same cell does not raise: it silently reports another
        employee's state, which is what the matrix exists to show correctly.

        A positional id (``row_number()`` over an unordered set) breaks this the
        moment any certification is created — every later row shifts up.
        """
        Status = self.env["cbet.employee.competency.status"]
        comps = [self._make_competency("RPT-4%d" % i) for i in range(5)]
        emp_a = self._make_employee("Cand Stable A")
        for comp in comps:
            self._certify(emp_a, comp, valid_to=Date.today() + relativedelta(years=1))

        before = {
            row.id: (row.employee_id.id, row.competency_id.id, row.state)
            for row in Status.search([("employee_id", "=", emp_a.id)])
        }
        self.assertEqual(len(before), len(comps))

        # An unrelated employee is certified on the same competencies. Nothing
        # about emp_a changed, so every one of its cells must still read the same.
        emp_b = self._make_employee("Cand Stable B")
        for comp in comps:
            self._certify(emp_b, comp, valid_to=Date.today() - relativedelta(days=30))

        self.env.invalidate_all()
        for row_id, (emp_id, comp_id, state) in before.items():
            row = Status.browse(row_id)
            self.assertEqual(
                (row.employee_id.id, row.competency_id.id), (emp_id, comp_id),
                "id %s no longer denotes the same cell" % row_id)
            self.assertEqual(row.state, state, "id %s reports another cell's state" % row_id)
