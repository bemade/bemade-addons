# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import is_html_empty

from odoo.addons.mail.tools.discuss import Store

PINNABLE_MESSAGE_TYPES = ("comment", "email", "email_outgoing")


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _chatter_pin_message_domain(self):
        self.ensure_one()
        return [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "in", PINNABLE_MESSAGE_TYPES),
        ]

    def message_set_pin(self, message_id, pinned):
        """(Un)pin a note or an email on this record's chatter.

        Silent on purpose: unlike ``discuss.channel.set_message_pin`` nothing is
        posted, and ``write_date`` is kept by updating ``pinned_at`` in SQL.

        :param int message_id: the message to (un)pin, posted on this record
        :param bool pinned: pin when true, unpin otherwise
        :return: store data with the message's new ``pinned_at``
        """
        self.ensure_one()
        if self._name == "discuss.channel":
            raise UserError(_("Use the channel's own pin feature for Discuss channels."))
        if not self.env.user._is_internal():
            raise AccessError(_("Only internal users can pin messages."))
        self.check_access("write")
        message = self.env["mail.message"].search(
            [("id", "=", message_id), *self._chatter_pin_message_domain()]
        )
        if not message or is_html_empty(message.body):
            raise UserError(_("Only notes and emails of this record can be pinned."))
        if bool(message.pinned_at) != bool(pinned):
            message.flush_recordset(["pinned_at"])
            # SQL rather than write(): pinning must not move write_date.
            self.env.cr.execute(
                "UPDATE mail_message SET pinned_at = %s WHERE id = %s",
                (fields.Datetime.now() if pinned else None, message.id),
            )
            message.invalidate_recordset(["pinned_at"])
            # Same channel as core message updates: the user's other open tabs.
            Store(bus_channel=message._bus_channel()).add(
                message, "pinned_at"
            ).bus_send()
        return Store().add(message, "pinned_at").get_result()

    def _thread_to_store(self, store: Store, fields, *, request_list=None):
        super()._thread_to_store(store, fields, request_list=request_list)
        if (
            not request_list
            or "pinnedMessages" not in request_list
            or self._name == "discuss.channel"
            or not self.env.user._is_internal()
        ):
            return
        Message = self.env["mail.message"].sudo(False)
        for thread in self:
            # Load pinned messages explicitly: they may be older than the
            # first page of the thread the chatter fetches.
            messages = Message.search(
                [*thread._chatter_pin_message_domain(), ("pinned_at", "!=", False)],
                order="pinned_at desc, id desc",
            )
            if messages:
                store.add(messages)
