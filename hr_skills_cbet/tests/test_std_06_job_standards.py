"""UC-STD-06 — A job position requires CBET standards.

AC1: hr.job.cbet_standard_ids lists the standards a role requires (inverse
     cbet.standard.job_ids); any role can require any standard.
AC2: every active employee holding the role gets a qualification on each
     required standard (from_job=True), recomputed at once.
AC3: changing an employee's role archives the old role's job qualifications
     (never deletes them); certificates stay.
AC4: qualifications created by hand (from_job=False) are never touched.
AC5: editing a role's standards adds / archives qualifications for its holders.
AC6: an archived employee gets no new job qualification and loses the
     job-derived ones; re-entering a role reactivates the archived row
     (no duplicate).
AC7: the training matrix counts only active qualifications as requirements,
     so the old role's gaps disappear and the new role's gaps appear.
AC8: the matrix 'expiring' horizon follows the company's
     cbet_expiry_horizon_months.
AC9: the hr.job.skill tie-back (UC-STD-05) keeps working beside it.
"""
from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdJobStandards(CbetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.c_whmis = cls._make_competency("JOB-01", validity_months=36)
        cls.c_height = cls._make_competency("JOB-02", validity_months=36)
        cls.c_lift = cls._make_competency("JOB-03", validity_months=36)
        cls.std_shop = cls._make_standard(
            "Synthetic shop safety", essentials=cls.c_whmis | cls.c_height)
        cls.std_lift = cls._make_standard("Synthetic forklift", essentials=cls.c_lift)
        cls.job_shop = cls.env["hr.job"].create({
            "name": "Synthetic shop hand",
            "cbet_standard_ids": [Command.set(cls.std_shop.ids)],
        })
        cls.job_lift = cls.env["hr.job"].create({
            "name": "Synthetic warehouse hand",
            "cbet_standard_ids": [Command.set(cls.std_lift.ids)],
        })
        cls.job_none = cls.env["hr.job"].create({"name": "Synthetic office hand"})

    def _quals(self, emp, active_test=True):
        return self.env["cbet.qualification"].with_context(
            active_test=active_test).search([("employee_id", "=", emp.id)])

    def _cell(self, emp, comp):
        self.env.flush_all()
        return self.env["cbet.employee.competency.status"].search([
            ("employee_id", "=", emp.id), ("competency_id", "=", comp.id)])

    # AC1 ------------------------------------------------------------------
    def test_inverse_on_standard(self):
        self.assertEqual(self.std_shop.job_ids, self.job_shop)
        self.assertEqual(self.job_shop.cbet_standard_ids, self.std_shop)

    # AC2 ------------------------------------------------------------------
    def test_employee_in_role_gets_qualifications(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic A", "job_id": self.job_shop.id})
        qual = self._quals(emp)
        self.assertEqual(qual.standard_id, self.std_shop)
        self.assertTrue(qual.from_job)
        self.assertEqual(qual.n_required, 2)
        self.assertEqual(qual.state, "in_progress")

    def test_batch_create(self):
        emps = self.env["hr.employee"].create([
            {"name": "Synthetic B%d" % i, "job_id": self.job_shop.id} for i in range(3)
        ] + [{"name": "Synthetic C", "job_id": self.job_none.id}])
        quals = self.env["cbet.qualification"].search(
            [("employee_id", "in", emps.ids)])
        self.assertEqual(len(quals), 3)
        self.assertEqual(quals.standard_id, self.std_shop)

    def test_existing_certificates_count_at_once(self):
        emp = self._make_employee("Synthetic D")
        self._certify(emp, self.c_whmis, valid_to=Date.today() + relativedelta(years=1))
        self._certify(emp, self.c_height, valid_to=Date.today() + relativedelta(years=1))
        emp.job_id = self.job_shop
        self.assertEqual(self._quals(emp).state, "qualified")

    # AC3 ------------------------------------------------------------------
    def test_role_change_archives_old_requirements(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic E", "job_id": self.job_shop.id})
        cert = self._certify(emp, self.c_whmis,
                             valid_to=Date.today() + relativedelta(years=1))
        old = self._quals(emp)
        emp.job_id = self.job_lift
        self.assertFalse(old.active)
        self.assertTrue(old.exists())
        self.assertEqual(self._quals(emp).standard_id, self.std_lift)
        self.assertTrue(cert.active)

    # AC4 ------------------------------------------------------------------
    def test_manual_qualification_untouched(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic F", "job_id": self.job_shop.id})
        manual = self.env["cbet.qualification"].create(
            {"employee_id": emp.id, "standard_id": self.std_lift.id})
        self.assertFalse(manual.from_job)
        emp.job_id = self.job_none
        self.assertTrue(manual.active)
        self.assertEqual(self._quals(emp), manual)
        # A role that requires a hand-made qualification's standard does not
        # take it over, and leaving that role does not archive it.
        emp.job_id = self.job_lift
        emp.job_id = self.job_none
        self.assertTrue(manual.active)

    # AC5 ------------------------------------------------------------------
    def test_editing_role_standards(self):
        emps = self.env["hr.employee"].create([
            {"name": "Synthetic G1", "job_id": self.job_none.id},
            {"name": "Synthetic G2", "job_id": self.job_none.id},
        ])
        self.assertFalse(self._quals(emps[0]))
        self.job_none.cbet_standard_ids = [Command.link(self.std_lift.id)]
        for emp in emps:
            self.assertEqual(self._quals(emp).standard_id, self.std_lift)
        self.job_none.cbet_standard_ids = [Command.clear()]
        for emp in emps:
            self.assertFalse(self._quals(emp))
            self.assertEqual(len(self._quals(emp, active_test=False)), 1)

    # AC6 ------------------------------------------------------------------
    def test_archived_employee(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic H", "job_id": self.job_shop.id})
        qual = self._quals(emp)
        emp.action_archive()
        self.assertFalse(qual.active)
        emp.action_unarchive()
        self.assertTrue(qual.active)
        self.assertEqual(len(self._quals(emp, active_test=False)), 1)

    def test_reentering_role_reactivates(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic I", "job_id": self.job_shop.id})
        qual = self._quals(emp)
        emp.job_id = self.job_none
        self.assertFalse(qual.active)
        emp.job_id = self.job_shop
        self.assertTrue(qual.active)
        self.assertEqual(len(self._quals(emp, active_test=False)), 1)

    # AC7 ------------------------------------------------------------------
    def test_matrix_follows_role(self):
        emp = self.env["hr.employee"].create(
            {"name": "Synthetic J", "job_id": self.job_shop.id})
        self._certify(emp, self.c_whmis, valid_to=Date.today() + relativedelta(years=1))
        self.assertTrue(self._cell(emp, self.c_whmis).is_required)
        self.assertEqual(self._cell(emp, self.c_height).state, "none")
        self.assertTrue(self._cell(emp, self.c_height).is_required)
        emp.job_id = self.job_lift
        self.env.invalidate_all()
        # Old role's gap gone, held certificate stays (no longer required).
        self.assertFalse(self._cell(emp, self.c_height))
        self.assertFalse(self._cell(emp, self.c_whmis).is_required)
        self.assertEqual(self._cell(emp, self.c_whmis).state, "valid")
        self.assertEqual(self._cell(emp, self.c_lift).state, "none")

    # AC8 ------------------------------------------------------------------
    def test_matrix_horizon_from_company(self):
        emp = self._make_employee("Synthetic K")
        self._certify(emp, self.c_lift, valid_to=Date.today() + relativedelta(months=5))
        self.env.company.cbet_expiry_horizon_months = 3
        self.env.invalidate_all()
        self.assertEqual(self._cell(emp, self.c_lift).state, "valid")
        self.env.company.cbet_expiry_horizon_months = 6
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(self._cell(emp, self.c_lift).state, "expiring")

    # AC9 ------------------------------------------------------------------
    def test_job_skill_tieback_still_works(self):
        skill = self._make_cert_skill("Synthetic shop cert")
        self.std_shop.skill_id = skill
        job_skill = self.env["hr.job.skill"].create({
            "job_id": self.job_shop.id,
            "skill_id": skill.id,
            "skill_type_id": skill.skill_type_id.id,
            "skill_level_id": skill.skill_type_id.skill_level_ids[:1].id,
        })
        self.assertIn(job_skill, self.job_shop.job_skill_ids)
        self.assertEqual(self.job_shop.cbet_standard_ids, self.std_shop)
