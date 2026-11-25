import base64

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestLinkDocumentToRecordTour(HttpCase):
    def test_link_document_to_record_tour(self):
        self.env["res.partner"].create({"name": "Client demo"})
        self.env["documents.document"].create(
            {
                "name": "Procédure interne",
                "type": "binary",
                "datas": base64.b64encode(b"hello").decode(),
            }
        )
        self.start_tour(
            "/odoo/action-documents.document_action",
            "link_document_to_record",
            login="admin",
        )
