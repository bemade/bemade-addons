from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ConversationInboxCaptureWizard(models.TransientModel):
    """The GTD funnel's primary capture dialog (task #3965, AC6 a/b/c/g):
    file a browsable inbox item as a new conversation, thread it into an
    existing one, or link it to any business record -- optionally
    reassigning in the same step. Quiet capture (AC7/AC8): posts an
    internal note, never re-notifies the original recipients, and maps
    the correspondent to the From partner, not the acting user.
    """

    _name = "conversation.inbox.capture.wizard"
    _description = "Capture Inbox Item"

    transport_id = fields.Many2one(
        "conversation.transport", required=True, readonly=True
    )
    external_id = fields.Char(required=True, readonly=True)
    subject = fields.Char(readonly=True)

    mode = fields.Selection(
        [
            ("new", "New Conversation"),
            ("existing", "Add to Existing Conversation"),
            ("link", "Link to a Record"),
        ],
        default="new",
        required=True,
    )
    conversation_id = fields.Many2one(
        "mail.conversation", string="Existing Conversation"
    )
    res_model_id = fields.Many2one("ir.model", string="Record Model")
    res_id = fields.Integer(string="Record ID")
    res_display_name = fields.Char(
        string="Record",
        compute="_compute_res_display_name",
        help="Name of the selected record, shown only when it exists and "
        "the current user may read it.",
    )

    user_id = fields.Many2one("res.users", string="Assign To")
    team_id = fields.Many2one("mail.conversation.team")

    @api.depends("res_model_id", "res_id")
    def _compute_res_display_name(self):
        for wizard in self:
            name = False
            try:
                model = wizard.res_model_id.model
                if model and wizard.res_id and model in self.env:
                    record = self.env[model].browse(wizard.res_id)
                    if record.exists() and record.has_access("read"):
                        name = record.display_name
            except Exception:  # noqa: BLE001 - never leak, never raise
                name = False
            wizard.res_display_name = name

    @api.model
    def action_open_for_item(self, transport_id, external_id, subject, mode):
        """Entry point for the inbox's three capture buttons (task #4144).

        Returns today's capture-wizard action, unchanged, unless the
        transport's ``record_link_mode`` is active and the message's
        Odoo-origin headers resolve to a record the user can read. Then:
        Suggest (or Automatic on a mailbox not set to file by default, or
        an explicit "Add to Existing") presets the wizard on that record;
        Automatic on a mailbox that files by default files and links at
        once and opens the conversation.
        """
        transport = self.env["conversation.transport"].browse(transport_id)
        context = {
            "default_transport_id": transport_id,
            "default_external_id": external_id,
            "default_subject": subject,
            "default_mode": mode,
        }
        wizard_action = {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "views": [[False, "form"]],
            "target": "new",
            "context": context,
        }
        if not transport.exists() or not transport._record_link_active():
            return wizard_action
        try:
            stub = transport._normalize(transport._fetch(external_id))
            kind, target = transport._resolve_record_from_headers(stub)
        except Exception:  # noqa: BLE001 - resolution never blocks capture
            kind, target = False, None
        if kind != "link":
            return wizard_action

        conversations = self.env["mail.conversation"]
        if (
            mode in ("new", "link")
            and transport.record_link_mode == "auto"
            and transport.default_file_in_odoo
        ):
            conversation = conversations._find_captured(transport, external_id)
            if not conversation:
                conversation = conversations._capture_stub(
                    transport, stub, mode="link", target=target
                )
                conversations._inbox_archive_after_capture(transport, external_id)
            return self._action_open_conversation(conversation)

        ir_model = self.env["ir.model"]._get(target._name)
        context["default_res_model_id"] = ir_model.id
        context["default_res_id"] = target.id
        if mode != "existing":
            context["default_mode"] = "link"
        return wizard_action

    @api.model
    def _action_open_conversation(self, conversation):
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation",
            "res_id": conversation.id,
            "view_mode": "form",
            "target": "current",
        }

    def _get_link_target(self):
        self.ensure_one()
        if not self.res_model_id or not self.res_id:
            raise UserError(_("Pick a record to link this captured item to."))
        target = self.env[self.res_model_id.model].browse(self.res_id)
        if not target.exists():
            raise UserError(_("That record could not be found."))
        return target

    def action_capture(self):
        self.ensure_one()
        target = False
        if self.mode == "existing":
            if not self.conversation_id:
                raise UserError(
                    _("Pick an existing conversation to add this item to.")
                )
            target = self.conversation_id
        elif self.mode == "link":
            target = self._get_link_target()

        raw = self.transport_id._fetch(self.external_id)
        stub = self.transport_id._normalize(raw)
        conversation = self.env["mail.conversation"]._capture_stub(
            self.transport_id, stub, mode=self.mode, target=target
        )
        if self.user_id or self.team_id:
            conversation.action_reassign(
                user=self.user_id or None, team=self.team_id or None
            )
        self.env["mail.conversation"]._inbox_archive_after_capture(
            self.transport_id, self.external_id
        )
        return self._action_open_conversation(conversation)
