from markupsafe import Markup

from odoo import Command, _, models
from odoo.exceptions import UserError


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    # ------------------------------------------------------------
    # Entry point (shared by the bound server action and the chatter
    # message action)
    # ------------------------------------------------------------

    def action_open_split_wizard(self, message_id=None):
        self.ensure_one()
        context = {"default_conversation_id": self.id}
        if message_id:
            context["default_message_id"] = message_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Split conversation"),
            "res_model": "conversation.split.wizard",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": context,
        }

    # ------------------------------------------------------------
    # The operation
    # ------------------------------------------------------------

    def _split_new_conversation_values(self, values=None):
        """Values for the conversation a split creates. Override hook:
        glue modules carry extra conversation-level fields by extending
        the returned dict."""
        self.ensure_one()
        values = values or {}
        result = {
            "name": values.get("name") or self.name,
            "user_id": (
                values["user_id"] if "user_id" in values else self.user_id.id
            ),
            "team_id": self.team_id.id,
            "tag_ids": [Command.set(self.tag_ids.ids)],
            "primary_transport_id": self.primary_transport_id.id,
            "state": "open",
        }
        if "external_visibility" in self._fields:
            result["external_visibility"] = self.external_visibility
        return result

    def _split_at_message(self, message, values=None, participants=None, links=None):
        """Move ``message`` and every later message owned by this
        conversation (higher ``mail.message`` id, i.e. chatter order) to a
        new conversation, which is returned.

        A reassignment: the messages keep their ids and every other
        field; only ``res_id`` changes. Posts one internal note on each
        side and never sends anything external.

        :param participants: list of dicts (``source_participant_id``,
            ``partner_id``, ``email``, ``kind``, ``role``) for the new
            conversation; ``None`` carries all of this conversation's.
        :param links: list of dicts (``res_model``, ``res_id``,
            ``reason``); ``None`` carries all of this conversation's.
        """
        self.ensure_one()
        # The authorization gate: everything below that needs sudo is
        # bounded by this check.
        self.check_access("write")
        message = message.sudo()
        if (
            len(message) != 1
            or message.model != self._name
            or message.res_id != self.id
        ):
            raise UserError(
                _("The split point must be a message of this conversation.")
            )
        # sudo only to enumerate: hidden user_notification rows must move
        # with the rest of the tail.
        owned = (
            self.env["mail.message"]
            .sudo()
            .search([("model", "=", self._name), ("res_id", "=", self.id)], order="id")
        )
        # The hidden "you have been assigned" notice does not count as
        # content: leaving only it behind would be an empty conversation.
        content = owned.filtered(lambda m: m.message_type != "user_notification")
        if not content or message.id <= content[0].id:
            raise UserError(
                _(
                    "You cannot split from the first message: the original "
                    "conversation would be left empty."
                )
            )
        to_move = owned.filtered(lambda m: m.id >= message.id)

        values = dict(values or {})
        values.setdefault("name", message.subject or self.name)
        new = self.with_context(
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            mail_auto_subscribe_no_notify=True,
        ).create(self._split_new_conversation_values(values))

        self._split_carry_participants(new, participants)
        self._split_carry_links(new, links)

        # Core refuses a model/res_id change to anyone but a system user;
        # the scoped sudo is limited to the computed set, after the write
        # check above.
        to_move.write({"res_id": new.id})
        self.env["ir.attachment"].sudo().search(
            [
                ("id", "in", to_move.attachment_ids.ids),
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ]
        ).write({"res_id": new.id})

        self.message_post(
            body=Markup(_("Continued in %s")) % new._get_html_link(),
            subtype_xmlid="mail.mt_note",
        )
        new.message_post(
            body=Markup(_("Split from %s")) % self._get_html_link(),
            subtype_xmlid="mail.mt_note",
        )
        return new

    def _split_carry_participants(self, new, participants):
        Participant = self.env["mail.conversation.participant"]
        if participants is None:
            participants = [
                {
                    "source_participant_id": p.id,
                    "partner_id": p.partner_id.id,
                    "email": p.email,
                    "kind": p.kind,
                    "role": p.role,
                }
                for p in self.participant_ids
            ]
        for entry in participants:
            vals = {
                "conversation_id": new.id,
                "partner_id": entry.get("partner_id") or False,
                "email": entry.get("email") or False,
            }
            for key in ("kind", "role"):
                if entry.get(key):
                    vals[key] = entry[key]
            source = Participant.browse(entry.get("source_participant_id")).exists()
            if source:
                # copy() carries scope fields added by other modules
                # (receives_updates, visibility, ...). Never subscribes.
                source.copy(vals)
            else:
                Participant.create(vals)

    def _split_carry_links(self, new, links):
        if links is None:
            links = [
                {"res_model": l.res_model, "res_id": l.res_id, "reason": l.reason}
                for l in self.link_ids
            ]
        Link = self.env["mail.conversation.link"]
        for entry in links:
            Link.create(
                {
                    "conversation_id": new.id,
                    "res_model": entry["res_model"],
                    "res_id": entry["res_id"],
                    "reason": entry.get("reason") or "manual",
                }
            )
