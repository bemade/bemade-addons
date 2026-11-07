from odoo.fields import Command
from odoo.tests import TransactionCase


class PartnerMergeBatchCase(TransactionCase):
    """Synthetic contacts only: this repository is public."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Wizard = cls.env["base.partner.merge.automatic.wizard"]
        # Core merges read every partner field, some of which (e.g. auth_signup's
        # signup_type) only Settings managers may read: in a full database only an
        # administrator can actually merge, so that is who merges in these tests.
        cls.admin = cls.env.ref("base.user_admin")
        # A non-admin contact manager: core's extra (email) check applies to them.
        cls.merger = cls.env["res.users"].create({
            "name": "Merge Tester",
            "login": "merge.batch.tester@example.com",
            "group_ids": [Command.set([
                cls.env.ref("base.group_user").id,
                cls.env.ref("base.group_partner_manager").id,
            ])],
        })

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _make_partners(self, count, email="dup@example.com", name="Duplicate"):
        return self.Partner.create([
            {"name": f"{name} {i}", "email": email} for i in range(count)
        ])

    def _merge(self, partners, dst=None, user=None):
        wizard = self.Wizard.with_user(user or self.admin)
        wizard._merge(partners.ids, dst_partner=dst)
        self.env.invalidate_all()

    def _assert_untouched(self, partners):
        self.env.invalidate_all()
        self.assertEqual(
            partners.exists(), partners,
            "A refused merge must leave every contact in place",
        )
