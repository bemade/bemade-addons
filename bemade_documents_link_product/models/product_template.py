from odoo import models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_product_document_domain(self):
        domain = super()._get_product_document_domain()
        Link = self.env["bemade.documents.link"]
        documents = Link._bemade_linked_documents(
            "product.template", self.ids
        ) | Link._bemade_linked_documents(
            "product.product", self.product_variant_ids.ids
        )
        return domain | Domain("ir_attachment_id", "in", documents.attachment_id.ids)
