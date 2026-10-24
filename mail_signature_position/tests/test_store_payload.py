"""Use case: the web client knows the current company's signature position.

Acceptance criteria
-------------------
* The store data sent to an internal user at web client start-up
  (``res.users._init_store_data``) carries a global ``mail_signature_position``
  value.
* That value is the one of the *current* company (``env.company``), so a user
  working in company B gets company B's choice.
* Default value ``below`` is sent when nothing was configured.
"""

from odoo.addons.mail.tools.discuss import Store
from odoo.fields import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStorePayload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Signature Store Co B"})
        cls.user = new_test_user(
            cls.env,
            login="sigpos_user",
            groups="base.group_user",
            company_id=cls.company_a.id,
            company_ids=[Command.set((cls.company_a + cls.company_b).ids)],
        )

    def _store_value(self, company):
        env = self.env(user=self.user, context={"allowed_company_ids": company.ids})
        store = Store()
        env["res.users"]._init_store_data(store)
        return store.get_result().get("Store", {}).get("mail_signature_position")

    def test_default_below_is_sent(self):
        self.assertEqual(self._store_value(self.company_a), "below")

    def test_current_company_value_is_sent(self):
        self.company_b.mail_signature_position = "above"
        self.assertEqual(self._store_value(self.company_b), "above")
        self.assertEqual(self._store_value(self.company_a), "below")
