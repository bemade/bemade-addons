from odoo import models
from odoo.fields import Domain


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _bemade_linked_documents_domain(self):
        self.ensure_one()
        return self.env["bemade.documents.link"]._bemade_linked_domain(
            "hr.employee", [self.id]
        )

    def _compute_document_count(self):
        """Add the linked documents the stock rule does not already count."""
        res = super()._compute_document_count()
        Document = self.env["documents.document"]
        for employee in self:
            if not employee.id:
                continue
            linked = employee._bemade_linked_documents_domain()
            if employee.company_id.documents_hr_settings:
                folder = employee.hr_employee_folder_id
                stock = Domain("id", "child_of", folder.ids) & Domain(
                    "type", "!=", "folder"
                )
            else:
                stock = Domain("partner_id", "in", employee.work_contact_id.ids)
            employee.document_count += Document.search_count(linked & ~stock)
        return res

    def action_open_documents(self):
        action = super().action_open_documents()
        self.ensure_one()
        linked = self._bemade_linked_documents_domain()
        if not self.company_id.documents_hr_settings:
            # Settings off: the stock client action filters on the work contact
            # and carries the upload defaults; keep its context, add linked docs.
            action["domain"] = list(Domain(action["domain"]) | linked)
            return action
        # Settings on: the stock action opens the employee folder. Keep it
        # unless some linked document lives outside of it.
        folder = self.hr_employee_folder_id
        stock = Domain("id", "child_of", folder.ids) & Domain("type", "!=", "folder")
        if not self.env["documents.document"].search_count(linked & ~stock):
            return action
        documents_action = self.env["ir.actions.actions"]._for_xml_id(
            "documents.document_action_preference"
        )
        return documents_action | {
            "domain": list(stock | linked),
            "context": {"searchpanel_default_user_folder_id": False},
        }
