# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: a member's role in a managed channel, the e-mail
dispatcher's marks (task 5546: the phone's too), and no calls for share
users."""
from odoo import _, fields, models
from odoo.exceptions import UserError


class DiscussChannelMember(models.Model):
    _inherit = 'discuss.channel.member'

    pk_role = fields.Selection(
        [('poster', 'Poster'), ('reader', 'Reader')], string="Portal Kit Role", index='btree_not_null',
        help="In a managed channel: a poster posts; a reader may only reply to a message. "
             "Empty: a normal member.")
    pk_emailed_message_id = fields.Many2one(
        'mail.message', string="Portal Kit Last E-mailed", ondelete='set null',
        help="The last message of the channel the kit's e-mail dispatcher handled for this member.")
    pk_pushed_message_id = fields.Many2one(
        'mail.message', string="Portal Kit Last Pushed", ondelete='set null',
        help="The last message of the channel sent to this member's phone (Web Push): the « each » "
             "e-mail skips the messages up to it.")
    pk_digest_date = fields.Date(
        string="Portal Kit Digest Date", help="The (local) day this member's conversation was last digested.")

    def _rtc_join_call(self, store=None, check_rtc_session_ids=None, camera=False):
        """No call for a share (portal) user: joining (and so starting) a
        call is refused."""
        for member in self:
            partner = member.partner_id
            if partner and not partner.user_ids.filtered(lambda user: not user.share):
                raise UserError(_("Calls are not available in the portal."))
        return super()._rtc_join_call(store=store, check_rtc_session_ids=check_rtc_session_ids, camera=camera)
