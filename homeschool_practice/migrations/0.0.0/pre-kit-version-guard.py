# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Stop an upgrade of homeschool_practice over a kit older than its code needs.

The homeschool app declares its entries per app (``app=``, ``_pk_apps()``),
which needs ``bemade_portal_kit`` 19.0.1.15.0 or later (``PK_MIN_VERSION``).
``-u homeschool_practice`` alone never upgrades the kit; a ``0.0.0`` script runs on
every upgrade of this module, first among its pre-migrations, and stops the run
before anything is written, naming the command that does it right (upgrade the
kit in the same run). Not run on a fresh install; a database without the kit
(it is installed in the same run) is never blocked.
"""
from odoo.addons.bemade_portal_kit.tools.version_guard import require_kit


def migrate(cr, version):
    require_kit(cr, caller='homeschool_practice')
