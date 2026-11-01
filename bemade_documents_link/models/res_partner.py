from odoo import models
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _bemade_documents_domain(self):
        self.ensure_one()
        return Domain("partner_id", "=", self.id) | self.env[
            "bemade.documents.link"
        ]._bemade_linked_domain("res.partner", [self.id])

    def _compute_document_count(self):
        Document = self.env["documents.document"]
        for partner in self:
            partner.document_count = (
                Document.search_count(partner._bemade_documents_domain())
                if partner.id
                else 0
            )

    def action_see_documents(self):
        action = super().action_see_documents()
        # The documents' owner contact (partner_id) is never rewritten by a
        # link, so widen the domain with the linked documents instead.
        action["domain"] = list(self._bemade_documents_domain())
        return action
