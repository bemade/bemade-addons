from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    bemade_link_ids = fields.One2many(
        "bemade.documents.link",
        "document_id",
        string="Linked Records",
    )
    bemade_linked_record_count = fields.Integer(
        compute="_compute_bemade_linked_record_count",
        store=True,
    )

    @api.depends("bemade_link_ids")
    def _compute_bemade_linked_record_count(self):
        # Rows are unique per (document, res_model, res_id), so their count
        # is exactly the number of distinct records this document is linked
        # to across every model.
        for document in self:
            document.bemade_linked_record_count = len(document.bemade_link_ids)

    def action_view_linked_records(self):
        self.ensure_one()
        return {
            "name": _("Linked Records"),
            "type": "ir.actions.act_window",
            "res_model": "bemade.documents.link",
            "view_mode": "list,form",
            "domain": [("document_id", "=", self.id)],
        }

    def _bemade_repoint_primary(self):
        """Called when the link row that is the current native primary
        (``res_model``/``res_id``) is removed: repoint the native primary to
        another remaining link row, or reset it to the empty marker of
        19.0 (``res_model``/``res_id`` False, matching a freshly-uploaded,
        unlinked document) if none remain."""
        self.ensure_one()
        remaining = self.bemade_link_ids
        if remaining:
            primary = remaining[0]
            self.write({"res_model": primary.res_model, "res_id": primary.res_id})
        else:
            self.write({"res_model": False, "res_id": False})

    def action_link_to_record(self, model=False):
        """Documents-side entry point: the stock
        version (enterprise/documents/models/documents_document.py) refuses
        to open the wizard at all when any selected document is already
        linked (``res_model != 'documents.document'``). Since a document can
        now be linked to many records, that refusal no longer applies --
        override it (not monkey-patch the base method) so only our subclass
        drops the guard.

        This is a full copy of the stock method minus the "already linked"
        early-return block; everything else -- context keys, the ``model``
        pre-selection branch, the returned act_window -- is unchanged.
        """
        context = {
            "default_document_ids": self.ids,
            "default_resource_ref": False,
            "default_is_readonly_model": False,
            "default_model_ref": False,
        }

        if model:
            self.env[model].check_access("write")
            context["default_is_readonly_model"] = True
            context["default_model_id"] = self.env["ir.model"]._get_id(model)
            first_valid_id = self.env[model].search([], limit=1).id
            if not first_valid_id:
                raise UserError(
                    _("There are no records to link this document. Create one first.")
                )
            context["default_resource_ref"] = f"{model},{first_valid_id}"

        return {
            "name": _("Choose a record to link"),
            "type": "ir.actions.act_window",
            "res_model": "documents.link_to_record_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": context,
        }

    def _bemade_is_shared(self):
        """True if any of these documents is linked to two or more records."""
        return any(len(document.bemade_link_ids) >= 2 for document in self)
