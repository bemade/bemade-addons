from odoo import models


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    def _bemade_ensure_product_document(self):
        """Ensure a ``product.document`` exists for the attachment of each of
        these documents.

        The product "Documents" button lists ``product.document`` records, not
        ``documents.document``. A document linked to a product afterwards has
        no such record, so create it, reusing the existing attachment.
        Idempotent."""
        documents = self.filtered("attachment_id")
        if not documents:
            return
        ProductDocument = self.env["product.document"].sudo()
        existing = ProductDocument.with_context(active_test=False).search(
            [("ir_attachment_id", "in", documents.attachment_id.ids)]
        )
        missing = documents.attachment_id - existing.ir_attachment_id
        if not missing:
            return
        # no_document: the attachment already has its documents.document, a
        # second one would violate documents_document_attachment_unique.
        ProductDocument.with_context(no_document=True).create(
            [{"ir_attachment_id": attachment.id} for attachment in missing]
        )
