"""Use case 2 - core safety checks still hold, on the whole set.

Acceptance criteria:
- A set where one contact is the parent of another is refused (UserError) and
  nothing is merged, even when parent and child would land in different
  batches.
- A set whose contacts are linked to two different users is refused and
  nothing is merged, even when the two users sit in different batches.
- A non-administrator merging contacts with different emails is refused and
  nothing is merged; the administrator may still do it.
- If a batch fails after earlier batches ran, the whole merge is cancelled
  (all-or-nothing).
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.base.wizard.base_partner_merge import (
    BasePartnerMergeAutomaticWizard as CoreWizard,
)

from .common import PartnerMergeBatchCase


@tagged("post_install", "-at_install")
class TestMergeSafety(PartnerMergeBatchCase):

    def _assert_refused_up_front(self, partners, dst, message, user=None):
        """The whole-set check refuses before any batch is merged."""
        core_merge = CoreWizard._merge
        calls = []

        def counting_merge(wizard, partner_ids, dst_partner=None, extra_checks=True):
            calls.append(list(partner_ids))
            return core_merge(wizard, partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

        with patch.object(CoreWizard, "_merge", counting_merge):
            with self.assertRaises(UserError) as cm:
                self._merge(partners, dst=dst, user=user)
        self.assertIn(message, str(cm.exception))
        self.assertFalse(calls, "No batch may run when the whole set is refused")
        self._assert_untouched(partners)

    def test_parent_child_in_set_refused(self):
        partners = self._make_partners(6)
        # last contact is the parent of the first: they fall in different batches
        partners[0].parent_id = partners[5]
        self._assert_refused_up_front(partners, partners[1], "parent")

    def test_two_users_across_batches_refused(self):
        partners = self._make_partners(7)
        for i, partner in ((1, partners[1]), (2, partners[6])):
            self.env["res.users"].create({
                "name": f"Linked {i}",
                "login": f"linked.batch.{i}@example.com",
                "partner_id": partner.id,
            })
        self._assert_refused_up_front(partners, partners[0], "more than one user")

    def test_different_emails_refused_for_non_admin(self):
        partners = self._make_partners(5)
        partners[4].email = "other@example.com"
        self._assert_refused_up_front(
            partners, partners[0], "same email", user=self.merger,
        )

    def test_different_emails_allowed_for_admin(self):
        partners = self._make_partners(5)
        partners[4].email = "other@example.com"
        self._merge(partners, dst=partners[0])
        self.assertEqual(partners.exists(), partners[0])

    @mute_logger("odoo.addons.base.wizard.base_partner_merge")
    def test_failure_in_later_batch_cancels_everything(self):
        partners = self._make_partners(7)
        core_merge = CoreWizard._merge
        calls = []

        def failing_merge(wizard, partner_ids, dst_partner=None, extra_checks=True):
            calls.append(list(partner_ids))
            if len(calls) == 3:
                raise UserError("batch failure")
            return core_merge(wizard, partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

        with patch.object(CoreWizard, "_merge", failing_merge):
            with self.assertRaises(UserError) as cm:
                self._merge(partners, dst=partners[0])
            self.assertIn("batch failure", str(cm.exception))
        self.assertEqual(len(calls), 3, "7 contacts run as 3 batches of up to 3")
        self.assertTrue(all(len(c) <= 3 and c[0] == partners[0].id for c in calls))
        self._assert_untouched(partners)
