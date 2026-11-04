from odoo import api, models

PRODUCT_MODELS = ("product.template", "product.product")


class BemadeDocumentsLink(models.Model):
    _inherit = "bemade.documents.link"

    @api.model_create_multi
    def create(self, vals_list):
        links = super().create(vals_list)
        product_links = links.filtered(lambda link: link.res_model in PRODUCT_MODELS)
        product_links.document_id.sudo()._bemade_ensure_product_document()
        return links
