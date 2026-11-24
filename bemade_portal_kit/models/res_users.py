# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models


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

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['pk_theme', 'pk_show_done_buttons']

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
