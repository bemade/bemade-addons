"""Site / work-order contacts lists can open the contact (task 4377).

Acceptance criteria:
- On the FSM task form, the sale order form and the contact form, the embedded
  list of ``site_contacts`` and ``work_order_contacts`` (served from
  ``bemade_fsm.fsm_contacts_view_list``) carries ``open_form_view="True"``, so
  each row shows Odoo's open arrow that opens the full contact in a dialog.
- That list stays ``editable="bottom"`` (inline editing of name/email/phone
  still works).

The click itself (arrow → dialog) is UI behaviour and is not covered here.
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestFSMContactsListView(TransactionCase):
    CONTACT_FIELDS = ("site_contacts", "work_order_contacts")

    def _assert_contacts_lists_open(self, model, view_xmlid):
        view = self.env.ref(view_xmlid)
        arch = self.env[model].get_view(view_id=view.id, view_type="form")["arch"]
        doc = etree.fromstring(arch)
        for fname in self.CONTACT_FIELDS:
            with self.subTest(model=model, field=fname):
                lists = doc.xpath(f"//field[@name='{fname}']/list")
                self.assertTrue(lists, f"{model}.{fname}: no embedded list in form")
                for list_node in lists:
                    self.assertEqual(list_node.get("open_form_view"), "True")
                    self.assertEqual(list_node.get("editable"), "bottom")

    def test_fsm_task_form_contacts_open(self):
        self._assert_contacts_lists_open("project.task", "project.view_task_form2")

    def test_sale_order_form_contacts_open(self):
        self._assert_contacts_lists_open("sale.order", "sale.view_order_form")

    def test_partner_form_contacts_open(self):
        self._assert_contacts_lists_open("res.partner", "base.view_partner_form")
