from odoo import models


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    def _bemade_sync_product_document(self):
        """Ensure a ``product.document`` exists for any of these documents that
        are linked to a product.

        The product "Documents" smart button reads the **``product.document``**
        model (filtered by ``res_model`` / ``res_id`` on the shared
        ``ir.attachment``), NOT ``documents.document``. When a file is uploaded
        from a product, the stock ``ir.attachment.create`` override creates the
        ``product.document`` for us; but when an *existing* ``documents.document``
        is merely *re-linked* to a product (the whole point of this module), only
        its ``res_model`` / ``res_id`` change — via a ``write`` that propagates to
        the attachment with ``no_document=True`` — so no ``product.document`` is
        ever created and the document never appears under the product's smart
        button (task #3678 defect 2).

        This bridges that gap: for each document now linked to a product and
        backed by a real attachment, create the matching ``product.document``
        (idempotently) so it surfaces on the product. The bridge is a soft
        dependency — it is a no-op when ``documents_product`` (which provides the
        ``product.document`` smart-button integration) is not installed.
        """
        ProductDocument = self.env.get("product.document")
        if ProductDocument is None:
            # documents_product not installed -> no product smart button to feed.
            return
        product_models = ("product.template", "product.product")
        to_bridge = self.filtered(
            lambda d: d.res_model in product_models
            and d.res_id
            and d.attachment_id
        )
        if not to_bridge:
            return
        # Only create what is missing — keep idempotent across repeated links.
        existing = self.env["product.document"].sudo().search(
            [("ir_attachment_id", "in", to_bridge.attachment_id.ids)]
        )
        existing_attachment_ids = set(existing.mapped("ir_attachment_id").ids)
        vals_list = [
            {"ir_attachment_id": doc.attachment_id.id}
            for doc in to_bridge
            if doc.attachment_id.id not in existing_attachment_ids
        ]
        if not vals_list:
            return
        # The attachment already carries res_model / res_id (propagated by
        # documents.document._inverse_res_model) AND already has its own
        # documents.document. Create the product.document with no_document=True
        # so the documents bridge does not try to create a SECOND
        # documents.document for the same attachment (which would violate the
        # documents_document_attachment_unique constraint).
        self.env["product.document"].sudo().with_context(
            no_document=True
        ).create(vals_list)
