from odoo import api, fields, models
from odoo.exceptions import AccessError


class ConversationTransport(models.Model):
    """Generic IMAP/SMTP provider: a manually-configured account
    authenticating with ``login``/``password`` against a host/port the user
    supplies.

    The browse/fetch/normalize/match/send implementation itself lives in
    ``conversation_email_base`` and is shared with every other
    email-speaking provider -- this module contributes only the connection
    *configuration* (task #3965): the ``provider`` code, the endpoint
    fields, and the password. It deliberately does **not** override
    ``_imap_oauth_string``: generic IMAP has no OAuth mechanism of its own,
    so the engine's ``None`` default (plain password login) is correct here.
    """

    _inherit = "conversation.transport"

    provider = fields.Selection(
        selection_add=[("imap", "IMAP / Generic Email")],
        ondelete={"imap": "cascade"},
        default="imap",
    )

    imap_host = fields.Char(string="IMAP Server")
    imap_port = fields.Integer(string="IMAP Port", default=993)
    imap_ssl = fields.Boolean(string="IMAP over SSL", default=True)
    smtp_host = fields.Char(string="SMTP Server")
    smtp_port = fields.Integer(string="SMTP Port", default=587)
    smtp_ssl = fields.Boolean(
        string="SMTP over STARTTLS",
        default=True,
        help="Use STARTTLS on the SMTP connection (the common case on port "
        "587). Leave off only for a plain/legacy relay.",
    )
    password = fields.Char(
        groups="base.group_system",
        help="IMAP/SMTP account password. Generic IMAP has no universal "
        "OAuth mechanism, so this stays a plain stored secret. Only "
        "administrators can read or write it; the owner of a personal "
        "transport sets theirs through the New Password field. Left blank on an "
        "OAuth-connected account (conversation_gmail, ...): those "
        "authenticate with a token instead, never a stored password.",
    )
    new_password = fields.Char(
        compute="_compute_new_password",
        inverse="_inverse_new_password",
        copy=False,
        help="Write-only. Sets the account password of your own transport "
        "without ever being able to read a stored password back.",
    )
    password_set = fields.Boolean(
        compute="_compute_password_set",
        help="Whether a password is stored for this account. Says nothing "
        "about its value.",
    )

    def _compute_new_password(self):
        # Write-only: never expose anything, whatever is stored.
        for transport in self:
            transport.new_password = False

    def _check_can_set_password(self, owner_ids):
        """Owner-can-set rule: a non-admin may set the password of a
        transport they own, never of a shared one. ``owner_ids`` are the
        ``user_id`` values *before* the write, so a single write cannot
        claim a shared transport and set its password in one go."""
        if self.env.user.has_group("base.group_system"):
            return
        if any(owner_id != self.env.user.id for owner_id in owner_ids):
            raise AccessError(
                self.env._(
                    "You can only set the password of your own transport; "
                    "shared mailboxes are managed by an administrator."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("new_password"):
                self._check_can_set_password([vals.get("user_id")])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("new_password"):
            self._check_can_set_password([t.user_id.id for t in self])
        return super().write(vals)

    def _inverse_new_password(self):
        for transport in self:
            if transport.new_password:
                transport.sudo().password = transport.new_password
        # Drop the written value from the cache so the same request (the
        # form's save-then-read round trip) never echoes it back.
        self.invalidate_recordset(["new_password"])

    @api.depends_context("uid")
    def _compute_password_set(self):
        for transport in self:
            transport.password_set = bool(transport.sudo().password)

    def _email_providers(self):
        return super()._email_providers() + ["imap"]

    def _email_connection_params(self):
        # Provider-guarded, not load-order-dependent: another provider
        # module's transports must keep their own endpoints even though
        # this module also extends conversation.transport.
        if self.provider != "imap":
            return super()._email_connection_params()
        return {
            "imap_host": self.imap_host,
            "imap_port": self.imap_port or 993,
            "imap_ssl": self.imap_ssl,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port or 587,
            "smtp_starttls": self.smtp_ssl,
            # sudo: the engine runs as the end user on shared mailboxes, who
            # cannot read the field; the value stays server-side.
            "password": self.sudo().password,
        }
