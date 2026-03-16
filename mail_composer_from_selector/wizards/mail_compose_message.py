# Copyright 2025 Bemade Inc.
# License Other proprietary.

from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    from_address_id = fields.Many2one(
        "mail.from.address",
        string="From Address",
        help="Select which authorized email address to use as the From address",
        compute="_compute_from_address_id",
        readonly=False,
        store=True,
    )

    @api.depends("composition_mode", "model", "res_ids", "template_id")
    def _compute_from_address_id(self):
        """Set default From address based on available addresses for the user."""
        for composer in self:
            if composer.from_address_id:
                continue
            allowed_addresses = self.env["mail.from.address"]._get_allowed_addresses()
            if len(allowed_addresses) == 1:
                composer.from_address_id = allowed_addresses[0]
            else:
                composer.from_address_id = False

    @api.onchange("from_address_id")
    def _onchange_from_address_id(self):
        """Update email_from when from_address_id changes."""
        if self.from_address_id:
            self.email_from = self.from_address_id.email
            # Update author_id based on the email
            if self.email_from:
                author, _ = self.env["mail.thread"]._message_compute_author(
                    None, self.email_from, raise_on_email=False
                )
                if author:
                    self.author_id = author

    @api.depends("composition_mode", "email_from", "model", "res_domain", "res_ids", "template_id")
    def _compute_authorship(self):
        """Override to use from_address_id email when set."""
        # First call super to get default behavior
        result = super()._compute_authorship()
        
        # Then override with from_address_id if set
        for composer in self:
            if composer.from_address_id:
                composer.email_from = composer.from_address_id.email
                # Try to find author based on the email
                author, _ = self.env["mail.thread"]._message_compute_author(
                    None, composer.email_from, raise_on_email=False
                )
                if author:
                    composer.author_id = author
        
        return result

    def _action_send_mail_comment(self, res_ids):
        """Ensure from_address_id email is used in sent mail."""
        self.ensure_one()
        
        # If from_address_id is set, make sure email_from uses it
        if self.from_address_id:
            self.email_from = self.from_address_id.email
        
        return super()._action_send_mail_comment(res_ids)