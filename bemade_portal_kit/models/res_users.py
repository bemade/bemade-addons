# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

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
