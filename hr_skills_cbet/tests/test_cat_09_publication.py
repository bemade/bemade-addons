"""UC-CAT-09 — Publication workflow (MVP core).

AC1: publishing bumps semantic version, stamps publication date, freezes an
     immutable snapshot of criteria/questions/protocol.
AC2: only published competencies can be evaluated (enforced in EVL).
AC4: state transitions restricted to Manager group.
"""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatPublication(CbetCommon):
    def test_publish_bumps_version_stamps_and_snapshots(self):
        c = self._make_competency("TST-90")
        self._add_criteria(c, [("security", "LOTO"), ("standard", "Rinse")])
        self.env["cbet.question"].create(
            {"competency_id": c.id, "text": "Q1", "essential": True})
        old_version = c.version

        c.with_user(self.manager).action_publish()

        self.assertEqual(c.state, "published")
        # First publication lands on 1.0.
        self.assertEqual(c.version, "1.0")
        self.assertTrue(c.publish_date)
        self.assertEqual(len(c.version_ids), 1)
        snap = c.version_ids.snapshot
        self.assertEqual(len(snap["units"][0]["criteria"]), 2)
        self.assertEqual(len(snap["questions"]), 1)

        # A subsequent publication bumps the minor (1.0 -> 1.1).
        c.with_user(self.manager).action_reset_to_draft()
        c.with_user(self.manager).action_publish()
        self.assertEqual(c.version, "1.1")
        self.assertEqual(len(c.version_ids), 2)

    def test_publish_requires_manager(self):
        c = self._make_competency("TST-91")
        user = self.env["res.users"].create({
            "name": "Plain", "login": "plain_user", "email": "p@example.com",
        })
        with self.assertRaises(UserError):
            c.with_user(user).action_publish()

    def test_snapshot_is_frozen_against_later_edits(self):
        c = self._make_competency("TST-92")
        self._add_criteria(c, [("standard", "Original")])
        c.with_user(self.manager).action_publish()
        # Editing criteria after publication must not change the frozen snapshot.
        c.criterion_ids[0].text = "Changed"
        self.assertEqual(
            c.version_ids.snapshot["units"][0]["criteria"][0]["text"], "Original")

    def test_snapshot_carries_the_documents(self):
        # The published version freezes the fiche sections, the procedure, the
        # job aids and the demo notes it was published with — not only the grid.
        c = self._make_competency("TST-93", procedure_body="<p>Step one</p>",
                                  demo_notes_body="<p>Show, then ask</p>",
                                  knowledge_body="<p>Theory</p>", subtitle="Recognition",
                                  protocol_start_conditions="Bench ready",
                                  maintenance_condition="3 jobs a year")
        self._add_criteria(c, [("standard", "Do")])
        pre = self._make_competency("TST-94")
        self.env["cbet.prerequisite"].create(
            {"competency_id": c.id, "prerequisite_id": pre.id, "prereq_type": "recommande"})
        icon = self.env["cbet.icon"].search([("token", "=", "epi-lunettes")])
        aid = self.env["cbet.job.aid"].create({"competency_id": c.id, "variant": "RO"})
        section = self.env["cbet.job.aid.section"].create({
            "job_aid_id": aid.id, "face": "recto", "kind": "ppe", "icon_id": icon.id,
            "name": "PPE", "note_html": "<p>note</p>"})
        self.env["cbet.job.aid.line"].create(
            {"section_id": section.id, "icon_id": icon.id, "text": "goggles"})

        c.with_user(self.manager).action_publish()
        snap = c.version_ids.snapshot
        self.assertEqual(snap["procedure_body"], "<p>Step one</p>")
        self.assertEqual(snap["demo_notes_body"], "<p>Show, then ask</p>")
        self.assertEqual(snap["knowledge_body"], "<p>Theory</p>")
        self.assertEqual(snap["subtitle"], "Recognition")
        self.assertEqual(snap["protocol"]["start_conditions"], "Bench ready")
        self.assertEqual(snap["validity"]["maintenance_condition"], "3 jobs a year")
        self.assertEqual(snap["prerequisites"], [{"code": "TST-94", "type": "recommande"}])
        self.assertEqual(snap["job_aids"], [{
            "id": aid.id, "variant": "RO",
            "sections": [{"face": "recto", "kind": "ppe", "icon": "epi-lunettes",
                          "name": "PPE", "note_html": "<p>note</p>",
                          "lines": [{"icon": "epi-lunettes", "text": "goggles"}]}],
        }])
        # frozen against later edits
        c.procedure_body = "<p>Step two</p>"
        section.line_ids.text = "shoes"
        snap = c.version_ids.snapshot
        self.assertEqual(snap["procedure_body"], "<p>Step one</p>")
        self.assertEqual(snap["job_aids"][0]["sections"][0]["lines"][0]["text"], "goggles")
