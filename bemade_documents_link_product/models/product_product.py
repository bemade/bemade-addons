from odoo import api, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _bemade_linked_attachment_ids(self):
        self.ensure_one()
        return (
            self.env["bemade.documents.link"]
            ._bemade_linked_documents("product.product", self.ids)
            .attachment_id.ids
        )

    def _compute_product_document_count(self):
        ProductDocument = self.env["product.document"]
        for product in self:
            product.product_document_count = ProductDocument.search_count(
                (
                    Domain("res_model", "=", "product.product")
                    & Domain("res_id", "=", product.id)
                )
                | Domain("ir_attachment_id", "in", product._bemade_linked_attachment_ids())
            )

    @api.readonly
    def action_open_documents(self):
        res = super().action_open_documents()
        res["context"]["bemade_variant_attachment_ids"] = (
            self._bemade_linked_attachment_ids()
        )
        return res
