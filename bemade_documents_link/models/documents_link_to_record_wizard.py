from odoo import models


class LinkToRecordWizard(models.TransientModel):
    _inherit = "documents.link_to_record_wizard"

    def link_to(self):
        """Extend the stock Documents-side link wizard so a document linked to a
        product also surfaces under the product's "Documents" smart button
        (task #3678 defect 2). This is the wizard our Documents-side
        "Link to Record" entry point opens.
        """
        res = super().link_to()
        self.document_ids._bemade_sync_product_document()
        return res
