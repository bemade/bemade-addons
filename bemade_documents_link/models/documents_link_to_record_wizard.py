from odoo import models


class LinkToRecordWizard(models.TransientModel):
    _inherit = "documents.link_to_record_wizard"

    def link_to(self):
        """Extend the stock Documents-side link wizard: create a
        ``bemade.documents.link`` row per document instead of overwriting the
        document's single native ``res_model``/``res_id`` pointer, so a
        document already linked to other records keeps those links (the
        native primary is synced by ``bemade.documents.link.create()``).
        Linking is idempotent, and the dialog closes once done.
        """
        self.ensure_one()
        target_model = self.resource_ref._name
        target_id = self.resource_ref.id

        Link = self.env["bemade.documents.link"]
        documents = self.document_ids.with_company(self.env.company)
        already_linked = Link.search(
            [
                ("document_id", "in", documents.ids),
                ("res_model", "=", target_model),
                ("res_id", "=", target_id),
            ]
        ).document_id
        to_link = documents - already_linked
        for document in to_link:
            Link.create(
                {
                    "document_id": document.id,
                    "res_model": target_model,
                    "res_id": target_id,
                }
            )
        documents.write({"is_editable_attachment": True})
        return {"type": "ir.actions.act_window_close"}
