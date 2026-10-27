import base64

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestLinkExistingDocumentTour(HttpCase):
    def test_link_existing_document_product_tour(self):
        if "product.document" not in self.env:
            self.skipTest("documents_product not installed")
        folder = self.env["documents.document"].create(
            {"name": "Product WS", "type": "folder"}
        )
        self.env.company.write(
            {"product_folder_id": folder.id, "documents_product_settings": True}
        )
        self.env["documents.document"].create(
            {
                "name": "Fiche technique",
                "type": "binary",
                "datas": base64.b64encode(b"hello").decode(),
            }
        )
        template = self.env["product.template"].create({"name": "Produit demo"})
        self.start_tour(
            f"/odoo/action-product.product_template_action_all/{template.id}",
            "link_existing_document_product",
            login="admin",
        )
