# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: editing the list on the contact form and the child-contact popup.

Acceptance criteria:
- The contact form and the child-contact popup show Phone and Mobile as
  text (phonebook widget ``partner_phone_list`` on the number list); the
  widget's dialog edits the number list (type, number, extension, label, drag
  handle). Phone stays in the view (invisible) for the views that extend it;
  Mobile and the SMS availability are loaded for the widget.
- The contacts list gives the Phone and Mobile columns a minimum width.
- Adding numbers on a new contact in the form saves them in order; Phone and
  Mobile follow the list.
- Typing a number in the form formats it like the standard Phone field
  (international form for a parsable number, raw value otherwise) and moves a
  typed extension to the extension column.
- A child contact created from the company form popup gets its own list.
- A list change that leaves Phone unchanged is logged in the chatter.
"""

from lxml import etree

from odoo.fields import Command
from odoo.tests import Form, tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestPartnerForm(PhoneListCase):
    def test_form_arch(self):
        arch = self.Partner.get_views([(False, "form")])["views"]["form"]["arch"]
        tree = etree.fromstring(arch)
        for scope in ("[not(ancestor::field)]", "[ancestor::field[@name='child_ids']]"):
            fields = tree.xpath("//field[@name='phone_ids']%s" % scope)
            self.assertEqual(len(fields), 1, scope)
            self.assertEqual(fields[0].get("widget"), "partner_phone_list")
            cols = [f.get("name") for f in fields[0].xpath("./list/field")]
            for col in ("sequence", "type", "number", "extension", "label"):
                self.assertIn(col, cols)
            for name in ("phone", "mobile", "phone_sms_available"):
                self.assertTrue(tree.xpath("//field[@name='%s']%s" % (name, scope)), (name, scope))
        list_arch = self.Partner.get_views([(False, "list")])["views"]["list"]["arch"]
        list_tree = etree.fromstring(list_arch)
        for name in ("phone", "mobile"):
            column = list_tree.xpath("//field[@name='%s']" % name)[0]
            self.assertEqual(column.get("widget"), "partner_phone_list_char")

    def test_simple_form_arch(self):
        """The simplified contact form (contact pop-ups opened from the mail
        composer, followers, calendar attendees, invitation wizards...) shows
        the phonebook widget instead of the plain Phone field."""
        view = self.env.ref("base.view_partner_simple_form")
        arch = self.Partner.get_view(view.id, "form")["arch"]
        tree = etree.fromstring(arch)
        fields = tree.xpath("//field[@name='phone_ids']")
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].get("widget"), "partner_phone_list")
        cols = [f.get("name") for f in fields[0].xpath("./list/field")]
        for col in ("sequence", "type", "number", "extension", "label"):
            self.assertIn(col, cols)
        phone = tree.xpath("//field[@name='phone']")
        self.assertEqual(len(phone), 1)
        self.assertEqual(phone[0].get("invisible"), "1")
        for name in ("mobile", "phone_sms_available"):
            self.assertTrue(tree.xpath("//field[@name='%s']" % name), name)

    def test_simple_form_create_with_lines(self):
        with Form(self.Partner, view="base.view_partner_simple_form") as form:
            form.name = "Sample Simple Person"
            form.email = "simple.person@example.com"
            with form.phone_ids.new() as line:
                line.type = "mobile"
                line.number = "+1 514 555 0171"
        partner = form.record
        self.assertEqual(partner.phone_ids.type, "mobile")
        self.assertEqual(partner.phone, "+1 514-555-0171")
        self.assertEqual(partner.mobile, partner.phone)

    def test_form_create_with_lines(self):
        with Form(self.Partner, view="base.view_partner_form") as form:
            form.name = "Sample Form Person"
            form.country_id = self.canada
            with form.phone_ids.new() as line:
                line.type = "mobile"
                line.number = "5145550161"
            with form.phone_ids.new() as line:
                line.type = "office"
                line.number = "514 555 0162 x 33"
                self.assertEqual(line.number, "+1 514-555-0162")
                self.assertEqual(line.extension, "33")
        partner = form.record
        self.assertEqual(
            self._numbers(partner),
            [("mobile", "+1 514-555-0161", False), ("office", "+1 514-555-0162", "33")],
        )
        self.assertEqual(partner.phone, "+1 514-555-0161")
        self.assertEqual(partner.mobile, "+1 514-555-0161")

    def test_form_unparsable_number_kept_raw(self):
        with Form(self.Partner, view="base.view_partner_form") as form:
            form.name = "Sample Raw"
            with form.phone_ids.new() as line:
                line.number = "call reception"
        self.assertEqual(form.record.phone, "call reception")

    def test_child_popup(self):
        with Form(self.Partner, view="base.view_partner_form") as form:
            form.name = "Sample Company"
            form.company_type = "company"
            form.country_id = self.canada
            with form.child_ids.new() as child:
                child.name = "Sample Child"
                with child.phone_ids.new() as line:
                    line.type = "mobile"
                    line.number = "514-555-0171"
        company = form.record
        self.assertEqual(company.child_ids.phone_ids.type, "mobile")
        self.assertEqual(company.child_ids.mobile, company.child_ids.phone)
        self.assertTrue(company.child_ids.phone)

    def test_list_change_logged(self):
        partner = self.Partner.with_context(tracking_disable=False).create(
            {"name": "Sample Logged", "phone": "514-555-0181"}
        )
        partner = partner.with_context(tracking_disable=False)
        before = len(partner.message_ids)
        partner.write({"phone_ids": [Command.create({"type": "fax", "number": "514-555-0189", "sequence": 99})]})
        self.assertEqual(partner.phone, "+1 514-555-0181")
        self.assertGreater(len(partner.message_ids), before)
        self.assertIn("514-555-0189", partner.message_ids[0].body)
