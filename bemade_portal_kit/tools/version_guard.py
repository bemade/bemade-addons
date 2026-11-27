# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Stop an upgrade that would run a kit dependent's code on an older kit.

Task 5388. Odoo has no version constraint on ``depends``, and
``odoo-bin -u <consumer>`` upgrades the consumer's dependents, never its
dependencies. On a database whose kit is older than its dependents' code
needs, ``-u <consumer>`` alone would install the new kit addons (pwa,
dashboard) and run the consumer's migrations against the OLD kit: they fail
half way, after Odoo committed the modules loaded before (Odoo commits per
module).

``require_kit`` is called as the FIRST statement of every install hook and
pre-migration of a kit dependent that moves data into the kit. It only
reads the kit's ``ir_module_module`` row and raises before anything is
written, with the command that does it right: upgrade the kit in the same
run. When the kit is part of the run, Odoo loads it first (it is a
dependency) and records its new version before the dependents' hooks run,
so the check passes. A fresh install (the kit absent, not installed yet, or
``to install`` in the same run) is never blocked.

``PK_MIN_VERSION`` is the single source of the minimum: the kit version
that the current dependents (this repository's kit addons and consumers)
need. A kit phase that its dependents start to rely on bumps it.
"""
import logging

from odoo.tools import config, parse_version

_logger = logging.getLogger(__name__)

KIT = 'bemade_portal_kit'
# Task 5391: the dependents declare their entries per app (``app=``).
# Task 5516: the notification preferences (bemade_portal_kit_chat).
# Task 5546: the phone switch, _pk_push_available (chat and pwa).
PK_MIN_VERSION = '19.0.1.18.0'

# States in which the kit's recorded version is the one the database holds.
_CHECKED_STATES = ('installed', 'to upgrade', 'to remove')


class PkKitVersionError(Exception):
    """The database's kit is older than a dependent's code needs."""


def _requested_upgrades():
    """The addons named on the command line (``-u``), for the hint."""
    update = config.get('update') or {}
    names = update.keys() if isinstance(update, dict) else str(update).split(',')
    return sorted(n.strip() for n in names if n and n.strip() and n.strip() not in (KIT, 'all'))


def require_kit(cr, minimum=PK_MIN_VERSION, caller='a kit dependent'):
    """Raise ``PkKitVersionError`` if the kit is installed at a version
    older than ``minimum``; no-op if it is new enough or not installed.

    Reads only; call it before any write of the hook or migration."""
    cr.execute('SELECT state, latest_version FROM ir_module_module WHERE name = %s', (KIT,))
    row = cr.fetchone()
    if not row or row[0] not in _CHECKED_STATES:
        return None
    found = row[1]
    if found and parse_version(found) >= parse_version(minimum):
        return None
    upgrades = ','.join([KIT] + (_requested_upgrades() or [caller]))
    message = (
        '%(caller)s needs %(kit)s >= %(minimum)s but the database has %(found)s. '
        'This run stopped before %(caller)s changed anything. '
        'Upgrade the kit in the same run: odoo-bin -u %(upgrades)s …'
    ) % {
        'caller': caller, 'kit': KIT, 'minimum': minimum,
        'found': found or 'an unknown version', 'upgrades': upgrades,
    }
    _logger.error(message)
    raise PkKitVersionError(message)
