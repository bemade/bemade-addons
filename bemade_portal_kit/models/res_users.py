# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Task 5200 (P5): the app's per-user preferences (« Settings »), set by
    # the user through /my/app/pref. A consumer may change the default theme
    # (``pk_theme = fields.Selection(default=...)`` in its own class).
    pk_theme = fields.Selection(
        selection=[('light', 'Light'), ('dark', 'Dark')],
        string="Portal App Theme",
        default='light',
        required=True,
        copy=False,
    )
    # Off by default: the edit cards' « Done » buttons are hidden and the
    # head pencil closes the card.
    pk_show_done_buttons = fields.Boolean(
        string="Show « Done » buttons",
        default=False,
        copy=False,
    )
    # Task 5546 (kit 1.18): the one-time « get notified on this phone? »
    # prompt was answered (either way): it never comes back, on any device.
    pk_push_prompted = fields.Boolean(
        string="Phone notification prompt answered",
        default=False,
        copy=False,
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['pk_theme', 'pk_show_done_buttons', 'pk_push_prompted']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['pk_theme', 'pk_show_done_buttons']

    def _pk_roles(self):
        """The user's app role SET: the roles of ``portal.kit._pk_roles()``
        whose groups (any-of) the user holds, united with
        ``_pk_extra_roles()``. Never cached (it is per user)."""
        self.ensure_one()
        roles = {
            role for role, spec in self.env['portal.kit']._pk_get_roles().items()
            if any(self.has_group(xmlid) for xmlid in spec['groups'])
        }
        roles.update(self._pk_extra_roles())
        return frozenset(roles)

    def _pk_extra_roles(self):
        """Roles resolved from anything but groups (a consumer's own data,
        e.g. a staff row). Extend with ``super()``; per user, never cached."""
        self.ensure_one()
        return frozenset()

    # ------------------------------------------------------------------
    # Task 5516 (kit 1.17): notification preferences
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_kind_default(kind, user):
        return kind['default_internal'] if not user.share else kind['default']

    def _pk_notification_mode(self, kind):
        """The user's mode for notification kind ``kind`` (a key): their
        stored choice when the kind still allows it, else the kind's
        ``default_internal`` (internal users) or ``default`` (share users);
        ``'off'`` for an unknown kind."""
        self.ensure_one()
        spec = self.env['portal.kit'].pk_notification_kind(kind)
        if not spec:
            return 'off'
        pref = self.env['portal.kit.notification.pref'].sudo().search(
            [('user_id', '=', self.id), ('kind', '=', kind)], limit=1)
        if pref and pref.mode in spec['modes']:
            return pref.mode
        return self._pk_kind_default(spec, self)

    def _pk_notification_users(self, kind, mode):
        """The users of ``self`` whose mode for ``kind`` is ``mode`` (one
        query for the stored rows)."""
        spec = self.env['portal.kit'].pk_notification_kind(kind)
        if not spec:
            return self if mode == 'off' else self.browse()
        stored = {
            pref.user_id.id: pref.mode
            for pref in self.env['portal.kit.notification.pref'].sudo().search(
                [('user_id', 'in', self.ids), ('kind', '=', kind)])
            if pref.mode in spec['modes']
        }
        return self.filtered(lambda user: stored.get(user.id, self._pk_kind_default(spec, user)) == mode)

    # ------------------------------------------------------------------
    # Task 5546 (kit 1.18): the phone switch of a kind of notification
    # ------------------------------------------------------------------
    def _pk_notification_push(self, kind):
        """Is the phone switch of notification kind ``kind`` (a key) on for
        the user? Off for a kind that does not declare ``push``, an unknown
        kind and without a stored row (the default)."""
        self.ensure_one()
        return bool(self._pk_notification_push_users(kind))

    def _pk_notification_push_users(self, kind):
        """The users of ``self`` whose phone switch of ``kind`` is on (one
        query)."""
        spec = self.env['portal.kit'].pk_notification_kind(kind)
        if not spec or not spec.get('push') or not self:
            return self.browse()
        on = self.env['portal.kit.notification.pref'].sudo().search(
            [('user_id', 'in', self.ids), ('kind', '=', kind), ('push', '=', True)]).user_id
        return self & on

    @api.model
    def _pk_notification_push_partners(self, kind, partners):
        """The partners of ``partners`` one of whose active users has the
        phone switch of ``kind`` on."""
        users = partners.sudo().user_ids.filtered('active')
        return users._pk_notification_push_users(kind).partner_id & partners

    def _pk_notification_set_push(self, kinds, value):
        """Set the phone switch of each of ``kinds`` (keys) to ``value`` for
        each user of ``self`` (sudo: a caller's own rows; the routes check
        the kinds)."""
        Pref = self.env['portal.kit.notification.pref'].sudo()
        for user in self:
            for kind in kinds:
                pref = Pref.search([('user_id', '=', user.id), ('kind', '=', kind)], limit=1)
                if pref:
                    if pref.push != bool(value):
                        pref.push = bool(value)
                else:
                    Pref.create({'user_id': user.id, 'kind': kind, 'push': bool(value)})
        return True
