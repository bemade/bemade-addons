# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: an internal user finds the portal users too in Discuss's
« start a conversation » search and the invite dialog (the core keeps to
internal users: ``user_ids.share = False``)."""
from odoo import models
from odoo.fields import Domain
from odoo.tools import SQL


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _search_for_channel_invite(self, store, search_term, channel_id=None, limit=30):
        if self.env.user.share:
            return super()._search_for_channel_invite(store, search_term, channel_id=channel_id, limit=limit)
        # The core's domain, without its « internal users only » condition:
        # every partner of an active user (internal or portal).
        domain = Domain.AND([
            Domain("name", "ilike", search_term) | Domain("email", "ilike", search_term),
            [('id', '!=', self.env.user.partner_id.id)],
            [("active", "=", True)],
            [("user_ids", "!=", False)],
            [("user_ids.active", "=", True)],
        ])
        channel = self.env["discuss.channel"]
        if channel_id:
            channel = self.env["discuss.channel"].search([("id", "=", int(channel_id))])
            domain &= Domain("channel_ids", "not in", channel.id)
            if channel.group_public_id:
                domain &= Domain("user_ids.all_group_ids", "in", channel.group_public_id.id)
        query = self._search(domain, limit=limit)
        query.order = SQL('LOWER(%s), "res_partner"."id"', self._field_to_sql(self._table, "name"))
        selectable_partners = self.env["res.partner"].browse(query)
        selectable_partners._search_for_channel_invite_to_store(store, channel)
        return {
            "count": self.env["res.partner"].search_count(domain),
            "partner_ids": selectable_partners.ids,
        }
