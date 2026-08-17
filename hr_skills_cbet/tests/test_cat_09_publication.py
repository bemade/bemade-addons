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
