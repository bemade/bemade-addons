# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516 (kit 1.17): a user's mode for one kind of notification.

A row exists only once the user chose a mode (« Settings ›
Notifications », ``POST /my/app/notify-pref``); without one the kind's
default applies (``res.users._pk_notification_mode``). A user reads and
writes only their own rows (ACL + record rules).

Task 5546 (kit 1.18): the same row holds the kind's phone switch
(``push``, off by default), independent of the e-mail mode: a row may hold
the switch only (``mode`` empty: the kind's default mode applies)."""
from odoo import fields, models


class PortalKitNotificationPref(models.Model):
    _name = 'portal.kit.notification.pref'
    _description = 'Portal Kit Notification Preference'
    _order = 'user_id, kind'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    kind = fields.Char(required=True)
    mode = fields.Char()
    push = fields.Boolean(string="On the phone")

    _pk_user_kind_unique = models.Constraint(
        'UNIQUE(user_id, kind)',
        'One notification preference per user and kind.',
    )
