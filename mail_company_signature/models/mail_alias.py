from odoo import models


class MailAlias(models.Model):
    _inherit = "mail.alias"

    def _mail_send_as_label(self):
        """Team name shown next to the person's name when sending as this alias.

        The display name of the alias's parent record (helpdesk team, sales
        team...), else the alias local part.
        """
        self.ensure_one()
        alias = self.sudo()
        model = alias.alias_parent_model_id.model
        if model and alias.alias_parent_thread_id and model in self.env:
            parent = self.env[model].sudo().browse(alias.alias_parent_thread_id).exists()
            if parent and parent.display_name:
                return parent.display_name
        return alias.alias_name or ""
