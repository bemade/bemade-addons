"""Acceptance criteria: ``dedup_key`` tracks the name.

1.  Creating a partner computes its key.
2.  Renaming a partner recomputes its key.
3.  Clearing the name clears the key to ``False``. Tested on an address-type
    child, since ``res_partner_check_name`` forbids a nameless contact.
4.  The key is stored, so the engine's raw SQL can read it.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDedupKeySync(TransactionCase):
    def test_01_computed_on_create(self):
        partner = self.env["res.partner"].create({"name": "Northwind Inc."})
        self.assertEqual(partner.dedup_key, "northwind")

    def test_02_recomputed_on_rename(self):
        partner = self.env["res.partner"].create({"name": "Northwind Inc."})
        partner.name = "Southwind Ltd"
        self.assertEqual(partner.dedup_key, "southwind")

    def test_03_cleared_with_the_name(self):
        parent = self.env["res.partner"].create({"name": "Northwind Inc."})
        # res_partner_check_name forbids a nameless *contact*; an address may
        # have no name of its own, which is the only way to exercise this.
        address = self.env["res.partner"].create(
            {"name": "Warehouse", "type": "delivery", "parent_id": parent.id}
        )
        self.assertEqual(address.dedup_key, "warehouse")
        address.name = False
        self.assertIs(address.dedup_key, False)

    def test_04_key_is_stored(self):
        field = self.env["res.partner"]._fields["dedup_key"]
        self.assertTrue(field.store, "the scan reads this column with raw SQL")
