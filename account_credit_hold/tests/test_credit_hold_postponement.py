"""Postponed credit holds.

Acceptance criteria:
- ``hold_postponed_until`` gives the date a postponed hold comes back, for a
  partner's own hold and for its company's hold, and is empty when the partner
  is actually on hold or not held at all.
- When both the company and the contact are postponed, the earliest date wins.
- "Today" is the user's local date: a postponement until the 20th still holds
  at 22:00 on the 19th in Montreal, although it is already the 20th in UTC.
- The cleanup cron never clears a postponement that is still running in some
  timezone.
"""
from datetime import date, timedelta

import freezegun

from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestCreditHoldPostponement(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.company = Partner.create({"name": "Postponed Co", "is_company": True})
        cls.contact = Partner.create({"name": "Postponed Contact", "parent_id": cls.company.id})
        cls.Partner = Partner.with_context(tz="UTC")

    def _read(self, partner, tz="UTC"):
        self.env.invalidate_all()
        return partner.with_context(tz=tz)

    def test_not_held(self):
        partner = self._read(self.company)
        self.assertFalse(partner.on_hold)
        self.assertFalse(partner.hold_postponed_until)

    def test_held_not_postponed(self):
        self.company.hold_bg = True
        for partner in (self.company, self.contact):
            partner = self._read(partner)
            self.assertTrue(partner.on_hold)
            self.assertFalse(partner.hold_postponed_until)

    def test_own_postponement(self):
        until = date.today() + timedelta(days=5)
        self.company.write({"hold_bg": True, "postpone_hold_until": until})
        partner = self._read(self.company)
        self.assertFalse(partner.on_hold)
        self.assertEqual(partner.hold_postponed_until, until)

    def test_company_postponement_covers_contact(self):
        until = date.today() + timedelta(days=5)
        self.company.write({"hold_bg": True, "postpone_hold_until": until})
        contact = self._read(self.contact)
        self.assertFalse(contact.on_hold)
        self.assertEqual(contact.hold_postponed_until, until)

    def test_earliest_postponement_wins(self):
        self.company.write({"hold_bg": True, "postpone_hold_until": date.today() + timedelta(days=9)})
        self.contact.write({"hold_bg": True, "postpone_hold_until": date.today() + timedelta(days=3)})
        contact = self._read(self.contact)
        self.assertFalse(contact.on_hold)
        self.assertEqual(contact.hold_postponed_until, date.today() + timedelta(days=3))

    def test_company_hold_beats_contact_postponement(self):
        self.company.hold_bg = True
        self.contact.write({"hold_bg": True, "postpone_hold_until": date.today() + timedelta(days=3)})
        contact = self._read(self.contact)
        self.assertTrue(contact.on_hold)
        self.assertFalse(contact.hold_postponed_until)

    def test_expired_postponement(self):
        self.company.write({"hold_bg": True, "postpone_hold_until": date.today() - timedelta(days=1)})
        partner = self._read(self.company)
        self.assertTrue(partner.on_hold)
        self.assertFalse(partner.hold_postponed_until)

    def test_local_date(self):
        self.company.write({"hold_bg": True, "postpone_hold_until": date(2026, 11, 20)})
        # 03:00 UTC on the 20th is 22:00 on the 19th in Montreal.
        with freezegun.freeze_time("2026-11-20 03:00:00"):
            montreal = self._read(self.company, tz="America/Montreal")
            self.assertFalse(montreal.on_hold)
            self.assertEqual(montreal.hold_postponed_until, date(2026, 11, 20))
            held = self.Partner.with_context(tz="America/Montreal").search([("on_hold", "=", True)])
            self.assertNotIn(self.company, held)

            utc = self._read(self.company, tz="UTC")
            self.assertTrue(utc.on_hold)
            held = self.Partner.search([("on_hold", "=", True)])
            self.assertIn(self.company, held)

    def test_user_timezone_without_context(self):
        self.company.write({"hold_bg": True, "postpone_hold_until": date(2026, 11, 20)})
        user = common.new_test_user(self.env, login="hold_tz_user", tz="America/Montreal")
        with freezegun.freeze_time("2026-11-20 03:00:00"):
            self.env.invalidate_all()
            partner = self.company.with_user(user).with_context(tz=False)
            self.assertFalse(partner.on_hold)

    def test_cleanup_keeps_running_postponements(self):
        self.company.postpone_hold_until = date(2026, 11, 20)
        self.contact.postpone_hold_until = date(2026, 11, 19)
        with freezegun.freeze_time("2026-11-20 03:00:00"):
            self.env["res.partner"]._cleanup_expired_hold_postponements()
        self.assertEqual(self.company.postpone_hold_until, date(2026, 11, 20))
        self.assertFalse(self.contact.postpone_hold_until)
