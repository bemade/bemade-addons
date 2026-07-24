"""UC-EVL-09/10 — Multi-unit assembly & certification issuance.

EVL-09 AC1: certification granted only when every required unit has a passed eval.
EVL-09 AC2: valid_from = date of the last required unit passed.
EVL-10 AC1: on qualifying pass a certification is created (version pinned, dates).
EVL-10 AC2: recertification supersedes the previous certification.
EVL-10 AC3: issuance triggers qualification recompute.
"""
from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlCertification(CbetCommon):
    def test_single_unit_issues_certification(self):
        comp = self._ready_competency("EVL-10", crit_specs=[("standard", "Do")])
        comp.validity_months = 24
        cand = self._make_employee("Cand 10")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi")
        self._sign_and_complete(ev, decision="reussi")

        cert = self.env["cbet.certification"].search(
            [("employee_id", "=", cand.id), ("competency_id", "=", comp.id)])
        self.assertEqual(len(cert), 1)
        self.assertEqual(cert.valid_from, ev.date)
        self.assertEqual(cert.valid_to, ev.date + relativedelta(months=24))
        self.assertTrue(cert.competency_version_id)
        self.assertIn(ev, cert.source_evaluation_ids)

    def test_multi_unit_requires_all_required_units(self):
        comp = self._ready_competency("EVL-11", crit_specs=[("standard", "Do")])
        unit_b = self.env["cbet.evaluation.unit"].create(
            {"competency_id": comp.id, "name": "Annexe B", "required": True})
        self.env["cbet.criterion"].create(
            {"unit_id": unit_b.id, "criterion_type": "standard", "text": "Do B"})
        cand = self._make_employee("Cand 11")

        # Pass unit A only → no certification yet.
        ev_a = self._make_evaluation(comp, cand, unit=comp.unit_ids.filtered("is_default"))
        self._set_results(ev_a, crit="reussi")
        self._sign_and_complete(ev_a, decision="reussi")
        self.assertFalse(self.env["cbet.certification"].search(
            [("employee_id", "=", cand.id), ("competency_id", "=", comp.id)]))

        # Pass unit B → certification issued, valid_from = last unit date.
        ev_b = self._make_evaluation(comp, cand, unit=unit_b)
        self._set_results(ev_b, crit="reussi")
        self._sign_and_complete(ev_b, decision="reussi")
        cert = self.env["cbet.certification"].search(
            [("employee_id", "=", cand.id), ("competency_id", "=", comp.id)])
        self.assertEqual(len(cert), 1)
        self.assertEqual(cert.valid_from, max(ev_a.date, ev_b.date))

    def test_recertification_supersedes_prior(self):
        comp = self._ready_competency("EVL-12", crit_specs=[("standard", "Do")])
        cand = self._make_employee("Cand 12")
        ev1 = self._make_evaluation(comp, cand)
        self._set_results(ev1, crit="reussi")
        self._sign_and_complete(ev1, decision="reussi")
        ev2 = self._make_evaluation(comp, cand)
        self._set_results(ev2, crit="reussi")
        self._sign_and_complete(ev2, decision="reussi")
        certs = self.env["cbet.certification"].with_context(active_test=False).search(
            [("employee_id", "=", cand.id), ("competency_id", "=", comp.id)])
        self.assertEqual(len(certs), 2)
        self.assertEqual(len(certs.filtered("active")), 1)

    def test_issuance_recomputes_qualification(self):
        comp = self._ready_competency("EVL-13", crit_specs=[("standard", "Do")])
        skill = self._make_cert_skill("Tech Classe I")
        std = self._make_standard("Classe I", essentials=comp, skill=skill)
        cand = self._make_employee("Cand 13")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi")
        self._sign_and_complete(ev, decision="reussi")
        qual = self.env["cbet.qualification"].search(
            [("employee_id", "=", cand.id), ("standard_id", "=", std.id)])
        self.assertEqual(qual.state, "qualified")
