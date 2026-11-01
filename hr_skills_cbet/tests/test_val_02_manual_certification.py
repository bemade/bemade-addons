"""UC-VAL-02 — A certificate entered by hand (recurring certifications).

AC1: the Valid / Expiring / Expired filters of the certification list work: the
     state can be searched with =, !=, in and not in (scalar or list).
AC2: « Valid until » defaults to valid_from + the competency's validity (or the
     company default when the competency has none); it stays editable, and an
     explicit value is kept.
AC3: creating an active certificate supersedes the employee's previous active
     certificate(s) on that competency when its valid_from is not older; an
     older back-dated entry does not supersede a newer one.
AC4: creating or editing a certificate recomputes the employee's existing
     qualifications that touch the competency.
AC5: the display name is « <employee> — <competency code> ».
"""
from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo.fields import Date
from odoo.tests import Form
from odoo.tests.common import tagged
from odoo.tools.safe_eval import safe_eval

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestValManualCertification(CbetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comp = cls._make_competency("VAL-20", validity_months=36)
        cls.emp = cls._make_employee("Synthetic Worker")
        cls.today = Date.today()

    def _cert(self, **vals):
        base = {"employee_id": self.emp.id, "competency_id": self.comp.id}
        base.update(vals)
        return self.env["cbet.certification"].create(base)

    # AC1 ------------------------------------------------------------------
    def test_state_search_operators(self):
        Cert = self.env["cbet.certification"]
        expired = self._cert(valid_from=self.today - relativedelta(years=4),
                             valid_to=self.today - relativedelta(days=10))
        other = self._make_competency("VAL-21")
        expiring = self._cert(competency_id=other.id,
                              valid_to=self.today + relativedelta(days=20))
        third = self._make_competency("VAL-22")
        valid = self._cert(competency_id=third.id,
                           valid_to=self.today + relativedelta(years=2))
        mine = [("employee_id", "=", self.emp.id)]
        self.assertEqual(Cert.search(mine + [("state", "=", "expired")]), expired)
        self.assertEqual(Cert.search(mine + [("state", "=", "expiring")]), expiring)
        self.assertEqual(Cert.search(mine + [("state", "=", "valid")]), valid)
        self.assertEqual(
            Cert.search(mine + [("state", "in", ["expired", "expiring"])]),
            expired | expiring)
        self.assertEqual(Cert.search(mine + [("state", "!=", "expired")]),
                         expiring | valid)
        self.assertEqual(
            Cert.search(mine + [("state", "not in", ["expired", "valid"])]), expiring)

    def test_list_view_filters_evaluate(self):
        view = self.env.ref("hr_skills_cbet.view_cbet_certification_search")
        arch = etree.fromstring(view.arch)
        filters = arch.xpath("//filter[@domain]")
        self.assertTrue(filters)
        for flt in filters:
            # Each filter must run without raising (the 19.0 ORM passes the
            # value as a collection).
            self.env["cbet.certification"].search(safe_eval(flt.get("domain")))

    # AC2 ------------------------------------------------------------------
    def test_valid_to_defaults_from_competency_validity(self):
        start = self.today - relativedelta(months=2)
        cert = self._cert(valid_from=start)
        self.assertEqual(cert.valid_to, start + relativedelta(months=36))

    def test_valid_to_falls_back_to_company_default(self):
        self.env.company.cbet_default_validity_months = 12
        comp = self._make_competency("VAL-23", validity_months=0)
        cert = self._cert(competency_id=comp.id, valid_from=self.today)
        self.assertEqual(cert.valid_to, self.today + relativedelta(months=12))

    def test_valid_to_explicit_value_is_kept_and_editable(self):
        explicit = self.today + relativedelta(months=5)
        cert = self._cert(valid_from=self.today, valid_to=explicit)
        self.assertEqual(cert.valid_to, explicit)
        with Form(self.env["cbet.certification"]) as form:
            form.employee_id = self.emp
            form.competency_id = self.comp
            form.valid_from = self.today
            self.assertEqual(form.valid_to, self.today + relativedelta(months=36))
            form.valid_to = explicit
        self.assertEqual(form.record.valid_to, explicit)

    # AC3 ------------------------------------------------------------------
    def test_new_certificate_supersedes_previous(self):
        old = self._cert(valid_from=self.today - relativedelta(years=3))
        new = self._cert(valid_from=self.today)
        self.assertFalse(old.active)
        self.assertTrue(new.active)
        self.assertEqual(old.state, "superseded")

    def test_backdated_entry_does_not_supersede_newer(self):
        new = self._cert(valid_from=self.today)
        old = self._cert(valid_from=self.today - relativedelta(years=3))
        self.assertTrue(new.active)
        self.assertTrue(old.active)

    def test_other_employee_or_competency_untouched(self):
        other_emp = self._make_employee("Synthetic Other")
        other_comp = self._make_competency("VAL-24")
        a = self._cert(valid_from=self.today - relativedelta(years=1))
        b = self._cert(employee_id=other_emp.id, valid_from=self.today)
        c = self._cert(competency_id=other_comp.id, valid_from=self.today)
        self.assertTrue(a.active and b.active and c.active)

    # AC4 ------------------------------------------------------------------
    def test_certificate_updates_existing_qualification(self):
        std = self._make_standard("Synthetic safety", essentials=self.comp)
        qual = self.env["cbet.qualification"].create(
            {"employee_id": self.emp.id, "standard_id": std.id})
        qual._recompute()
        self.assertEqual(qual.state, "in_progress")
        cert = self._cert(valid_from=self.today)
        self.assertEqual(qual.state, "qualified")
        cert.valid_to = self.today - relativedelta(days=1)
        self.assertEqual(qual.state, "suspended")
        cert.valid_to = self.today + relativedelta(years=1)
        self.assertEqual(qual.state, "qualified")
        cert.active = False
        self.assertEqual(qual.state, "suspended")

    def test_certificate_does_not_create_qualification(self):
        self._make_standard("Synthetic unrelated", essentials=self.comp)
        self._cert(valid_from=self.today)
        self.assertFalse(self.env["cbet.qualification"].search(
            [("employee_id", "=", self.emp.id)]))

    # AC5 ------------------------------------------------------------------
    def test_display_name(self):
        cert = self._cert(valid_from=self.today)
        self.assertEqual(cert.display_name, "Synthetic Worker — VAL-20")
