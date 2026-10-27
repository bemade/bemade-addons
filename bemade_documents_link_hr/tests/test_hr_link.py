import base64
import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHrLink(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Linked Employee"})

    def _doc(self, **vals):
        return self.env["documents.document"].create(
            {
                "name": "Doc",
                "type": "binary",
                "datas": base64.b64encode(b"hello").decode(),
                **vals,
            }
        )

    def _link(self, doc):
        self.env["documents.link.wizard"].with_context(
            active_model="hr.employee", active_id=self.employee.id
        ).create({"document_ids": [(4, doc.id)]}).action_link()

    def test_settings_off(self):
        self.employee.company_id.documents_hr_settings = False
        self.employee.invalidate_recordset()
        before = self.employee.document_count
        doc = self._doc()
        self._link(doc)
        self.employee.invalidate_recordset(["document_count"])
        self.assertEqual(self.employee.document_count, before + 1)
        action = self.employee.action_open_documents()
        json.dumps(action["domain"])
        found = self.env["documents.document"].search(action["domain"])
        self.assertIn(doc, found)
        own = self._doc(partner_id=self.employee.work_contact_id.id)
        self.employee.invalidate_recordset(["document_count"])
        action = self.employee.action_open_documents()
        found = self.env["documents.document"].search(action["domain"])
        self.assertIn(own, found)
        self.assertIn(doc, found)
        self.assertEqual(
            action["context"]["default_partner_id"], self.employee.work_contact_id.id
        )
        self.assertEqual(len(found), self.employee.document_count)
        self.assertIn(doc.attachment_id, self.employee._get_mail_thread_data_attachments())

    def test_settings_on(self):
        company = self.employee.company_id
        company.documents_hr_settings = True
        if not self.employee.hr_employee_folder_id:
            self.employee._generate_employee_documents_folders()
        if not self.employee.hr_employee_folder_id:
            self.skipTest("no employee folder can be generated")
        self.employee.invalidate_recordset()
        before = self.employee.document_count
        self.assertEqual(
            self.employee.action_open_documents()["type"], "ir.actions.act_url"
        )
        doc = self._doc()
        self._link(doc)
        self.employee.invalidate_recordset(["document_count"])
        self.assertEqual(self.employee.document_count, before + 1)
        action = self.employee.action_open_documents()
        self.assertNotEqual(action["type"], "ir.actions.act_url")
        json.dumps(action["domain"])
        self.assertIn(doc, self.env["documents.document"].search(action["domain"]))
