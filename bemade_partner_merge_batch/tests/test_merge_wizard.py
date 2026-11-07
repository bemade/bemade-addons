"""Use case 3 - Contacts > select N > Actions > Merge.

Acceptance criteria:
- Opening the merge wizard on 5 selected contacts and clicking "Merge
  Contacts" merges them all into the destination shown in the wizard, without
  the "more than 3 contacts" error.
"""
from odoo.tests import Form, tagged

from .common import PartnerMergeBatchCase


@tagged("post_install", "-at_install")
class TestMergeWizard(PartnerMergeBatchCase):

    def test_wizard_merges_five(self):
        partners = self._make_partners(5)
        Wizard = self.Wizard.with_user(self.admin).with_context(
            active_model="res.partner", active_ids=partners.ids,
        )
        form = Form(Wizard)
        self.assertEqual(len(form.partner_ids), 5)
        form.dst_partner_id = partners[3]
        wizard = form.save()
        wizard.action_merge()
        self.env.invalidate_all()
        self.assertEqual(partners.exists(), partners[3])
