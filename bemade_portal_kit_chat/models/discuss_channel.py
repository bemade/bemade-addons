# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: managed channels, the reply-only rule and the core gates on
``discuss.channel``.

* ``pk_managed_key``: set = a channel the consumer manages
  (``portal.kit._pk_chat_sync``); unique when set.
* Reply-only (uid-based, every route): in a managed channel a member whose
  role is ``reader`` may only post a ``comment`` whose parent is a message
  of the same channel (``message_post``; raw ``mail.message.create`` in
  ``mail_message.py``). Posters and internal users are unrestricted.
* Direct chats: a share user never creates one through Discuss
  (``_get_or_create_chat``); the kit's route does, after its contacts check
  (context ``pk_chat_start``).
* Discuss's own mention / ``@everyone`` e-mail to SHARE partners is dropped
  in chats and groups: their e-mail comes from the kit's preferences only.
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError

PK_CHAT_TYPES = ('chat', 'group')


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    pk_managed_key = fields.Char(
        string="Portal Kit Managed Key", index='btree_not_null', copy=False, readonly=True,
        help="Set: a group channel managed by a portal kit consumer (members and roles are synced).")

    _pk_managed_key_unique = models.Constraint(
        'UNIQUE(pk_managed_key)',
        'A managed key names one channel only.',
    )

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------
    def _pk_chat_member_of(self, partner):
        """The member of ``partner`` in this channel (sudo), or an empty
        recordset."""
        self.ensure_one()
        return self.env['discuss.channel.member'].sudo().search(
            [('channel_id', '=', self.id), ('partner_id', '=', partner.id)], limit=1)

    def _pk_chat_is_reader(self, user=None):
        """Is ``user`` (default: the current user) a reader of this managed
        channel? Internal users never are."""
        self.ensure_one()
        user = user or self.env.user
        if not self.sudo().pk_managed_key or user._is_internal() or user._is_public():
            return False
        return self._pk_chat_member_of(user.partner_id).pk_role == 'reader'

    def _pk_chat_check_post(self, message_type, parent_id):
        """Raise ``AccessError`` when the current user (a reader) may not
        post this message here: anything but a reply (``comment`` whose
        parent is a message of this channel)."""
        self.ensure_one()
        if not self._pk_chat_is_reader():
            return
        if message_type == 'comment' and parent_id:
            parent = self.env['mail.message'].sudo().browse(int(parent_id)).exists()
            if parent and parent.model == self._name and parent.res_id == self.id:
                return
        raise AccessError(_("In this group you can only reply to a message."))

    def message_post(self, *, message_type="notification", partner_ids=None, **kwargs):
        for channel in self:
            channel._pk_chat_check_post(message_type, kwargs.get('parent_id'))
        return super().message_post(message_type=message_type, partner_ids=partner_ids, **kwargs)

    # ------------------------------------------------------------------
    # Direct chats: through the kit route only for share users
    # ------------------------------------------------------------------
    def _get_or_create_chat(self, partners_to, pin=True):
        if self.env.user.share and not self.env.context.get('pk_chat_start'):
            raise AccessError(_("Start a conversation from the portal."))
        return super()._get_or_create_chat(partners_to, pin=pin)

    # ------------------------------------------------------------------
    # No Discuss mention e-mail to share partners in chats and groups
    # ------------------------------------------------------------------
    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)
        if self.channel_type not in PK_CHAT_TYPES:
            return recipients
        return [r for r in recipients if not (r.get('notif') == 'email' and (r.get('share') or r.get('ushare')))]
