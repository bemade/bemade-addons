from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DocumentsLinkWizard(models.TransientModel):
    """Record-side wizard: link one or more existing, unlinked
    ``documents.document`` records to the record the user is currently on
    (resolved from the ``active_model`` / ``active_id`` context).
    """

    _name = "documents.link.wizard"
    _description = "Link Existing Documents to Record"

    res_model = fields.Char(
        string="Target Model",
        required=True,
        default=lambda self: self.env.context.get("active_model"),
    )
    res_id = fields.Integer(
        string="Target Record",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    document_ids = fields.Many2many(
        "documents.document",
        string="Documents",
        # Offer only existing, not-yet-linked documents. An app-managed
        # document that isn't linked to a business record carries the
        # self-referential res_model 'documents.document' (set on create in
        # enterprise `documents`), so that — not False — is the "unlinked" marker.
        domain=[("res_model", "=", "documents.document")],
    )

    def action_link(self):
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_("Select at least one document to link."))

        # Gate on the user's *write* access to the target record, mirroring the
        # stock Documents link wizard's access logic, so a user cannot link a
        # document to a record they are not allowed to modify.
        target_model = self.res_model
        if target_model not in self.env or self.env[target_model]._abstract:
            raise UserError(_("Cannot link documents to model %s.", target_model))
        target = self.env[target_model].browse(self.res_id)
        if not target.exists():
            raise UserError(_("The record to link the documents to no longer exists."))
        target.check_access("write")

        # res_name recomputes automatically from res_model/res_id on
        # documents.document; mirror the stock wizard's write payload.
        self.document_ids.write({
            "res_model": self.res_model,
            "res_id": self.res_id,
            "is_editable_attachment": True,
        })
        # Surface the link under a product's "Documents" smart button (#3678).
        self.document_ids._bemade_sync_product_document()
        return {"type": "ir.actions.act_window_close"}
