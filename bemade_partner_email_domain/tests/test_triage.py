"""Ambiguous match and the Unassigned contacts list.

Acceptance criteria:
- Two divisions on the same domain: no parent written, exactly one open row
  listing both as candidates, nothing chosen by default.
- A second email change refreshes the same row (still one row per contact).
- Apply assignments writes only the rows with a choice, posts a bilingual
  note and closes them; untouched rows stay.
- A manual parent edit closes the row; so does a merge into a contact that
  has a company.
- The chosen company must be one of the candidates.
- Email changed to an unmatched domain drops the row.
- The weekly reminder creates one To-Do for the configured user while rows
  are open, and none when no user is configured.
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import EmailDomainCase


@tagged("post_install", "-at_install")
class TestTriage(EmailDomainCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.div_a = cls._company("Division A", "split.test")
        cls.div_b = cls._company("Division B", "split.test")

    def test_two_divisions_one_row(self):
        contact = self._contact("a@split.test")
        self.assertFalse(contact.parent_id)
        row = self._rows(contact)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.candidate_ids, self.div_a | self.div_b)
        self.assertFalse(row.chosen_parent_id)
        self.assertEqual(row.source, "create")
        contact.email = "b@split.test"
        self.assertEqual(len(self._rows(contact)), 1)
        self.assertEqual(self._rows(contact).source, "email")

    def test_apply_only_chosen_rows(self):
        chosen = self._contact("a@split.test")
        untouched = self._contact("b@split.test")
        self._rows(chosen).chosen_parent_id = self.div_b
        self.Suggestion.action_apply_assignments()
        self.assertEqual(chosen.parent_id, self.div_b)
        self.assertFalse(self._rows(chosen))
        self.assertFalse(untouched.parent_id)
        self.assertTrue(self._rows(untouched))
        body = chosen.message_ids[:1].body
        self.assertIn("Rattaché à", body)
        self.assertIn("Attached to", body)

    def test_manual_parent_closes_row(self):
        contact = self._contact("a@split.test")
        contact.parent_id = self.div_a
        self.assertFalse(self._rows(contact))

    def test_merge_closes_row(self):
        contact = self._contact("a@split.test")
        twin = self.Partner.create({"name": "Twin", "email": "a@other.test", "parent_id": self.div_a.id})
        wizard = self.env["base.partner.merge.automatic.wizard"].create({})
        wizard._merge((contact | twin).ids, twin)
        self.assertFalse(self.Suggestion.search([("partner_id", "=", contact.id)]))

    def test_choice_restricted_to_candidates(self):
        stranger = self._company("Stranger Test", "stranger.test")
        row = self._rows(self._contact("a@split.test"))
        with mute_logger("odoo.sql_db"), self.assertRaises(ValidationError):
            row.chosen_parent_id = stranger
            row.flush_recordset()

    def test_email_to_unmatched_domain_drops_row(self):
        contact = self._contact("a@split.test")
        contact.email = "a@nowhere.test"
        self.assertFalse(self._rows(contact))

    def test_weekly_reminder(self):
        self._contact("a@split.test")
        Activity = self.env["mail.activity"]
        domain = [("res_model", "=", "partner.parent.suggestion")]
        self.Suggestion._cron_remind_open_rows()
        self.assertFalse(Activity.search(domain))
        user = self.env["res.users"].create({"name": "Reminder Test", "login": "reminder_test"})
        self.env["ir.config_parameter"].sudo().set_param("bemade_partner_email_domain.reminder_user_id", user.id)
        self.Suggestion._cron_remind_open_rows()
        self.Suggestion._cron_remind_open_rows()
        activity = Activity.search(domain)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, user)
