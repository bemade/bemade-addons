# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5388: an upgrade that would run a kit dependent's new code on an
older kit stops before it writes anything.

Odoo has no version constraint on ``depends``, and ``-u <consumer>``
upgrades the consumer's dependents, not its dependencies: on a database
whose kit is older than the dependents' code needs, their install hooks
and migrations would run against the old kit and commit part of the move.

Acceptance criteria:

* UC-V1 The kit installed (or ``to upgrade``) at a version older than the
  minimum: ``require_kit`` raises, and the message names the caller, the
  minimum, the version found, and the ``-u bemade_portal_kit,…`` hint.
* UC-V2 The kit at the minimum or newer: no-op.
* UC-V3 The kit absent, uninstalled or ``to install`` (a fresh install,
  the kit installed in the same run): no-op.
* UC-V4 Versions compare numerically (``19.0.1.9.0`` < ``19.0.1.14.0``),
  never as strings.
* UC-V5 The guard only reads: it runs no write statement.
* UC-V6 One source for the minimum (``PK_MIN_VERSION``), the version
  the dependents of this kit's code need; the kit's own manifest is at
  least that.
"""
from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged
from odoo.tools import parse_version
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_portal_kit.tools.version_guard import (
    PK_MIN_VERSION, PkKitVersionError, require_kit,
)

KIT = 'bemade_portal_kit'


class _StubCursor:
    """A cursor that answers the kit's row (or none) and records queries."""

    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append(query)

    def fetchone(self):
        return self.row


@tagged('post_install', '-at_install')
class TestPkVersionGuard(TransactionCase):

    def _set_kit(self, state, version):
        self.env.cr.execute(
            'UPDATE ir_module_module SET state = %s, latest_version = %s WHERE name = %s',
            (state, version, KIT))

    # UC-V1
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_older_installed_kit_raises_with_the_hint(self):
        self._set_kit('installed', '19.0.1.2.0')
        with self.assertRaises(PkKitVersionError) as ctx:
            require_kit(self.env.cr, '19.0.1.14.0', 'bemade_portal_kit_pwa')
        msg = str(ctx.exception)
        self.assertIn('bemade_portal_kit_pwa needs bemade_portal_kit >= 19.0.1.14.0', msg)
        self.assertIn('the database has 19.0.1.2.0', msg)
        self.assertIn('-u bemade_portal_kit,', msg)
        self.assertIn('before bemade_portal_kit_pwa changed anything', msg)

    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_older_kit_to_upgrade_raises(self):
        self._set_kit('to upgrade', '19.0.1.13.0')
        with self.assertRaises(PkKitVersionError):
            require_kit(self.env.cr, '19.0.1.14.0', 'bemade_sports_clinic')

    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_default_minimum_is_the_constant(self):
        self._set_kit('installed', '19.0.1.2.0')
        with self.assertRaises(PkKitVersionError) as ctx:
            require_kit(self.env.cr, caller='bemade_portal_kit_dashboard')
        self.assertIn('>= %s' % PK_MIN_VERSION, str(ctx.exception))

    # UC-V2
    def test_equal_or_newer_is_a_noop(self):
        for version in ('19.0.1.14.0', '19.0.1.14.1', '19.0.1.15.0', '19.0.2.0.0'):
            self._set_kit('installed', version)
            self.assertIsNone(require_kit(self.env.cr, '19.0.1.14.0', 'x'))

    # UC-V3
    def test_absent_uninstalled_or_to_install_is_a_noop(self):
        self.assertIsNone(require_kit(_StubCursor(None), '19.0.1.14.0', 'x'))
        for state, version in (('uninstalled', '19.0.1.2.0'), ('uninstalled', None),
                               ('to install', None), ('to install', '19.0.1.2.0')):
            self._set_kit(state, version)
            self.assertIsNone(require_kit(self.env.cr, '19.0.1.14.0', 'x'))

    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_installed_without_version_raises(self):
        # An installed kit with no recorded version is not known to be new enough.
        self._set_kit('installed', None)
        with self.assertRaises(PkKitVersionError):
            require_kit(self.env.cr, '19.0.1.14.0', 'x')

    # UC-V4
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_numeric_comparison(self):
        self._set_kit('installed', '19.0.1.9.0')
        with self.assertRaises(PkKitVersionError):
            require_kit(self.env.cr, '19.0.1.14.0', 'x')
        self._set_kit('installed', '19.0.1.14.0')
        self.assertIsNone(require_kit(self.env.cr, '19.0.1.9.0', 'x'))

    # UC-V5
    @mute_logger('odoo.addons.bemade_portal_kit.tools.version_guard')
    def test_guard_only_reads(self):
        cr = _StubCursor(('installed', '19.0.1.2.0'))
        with self.assertRaises(PkKitVersionError):
            require_kit(cr, '19.0.1.14.0', 'x')
        self.assertEqual(len(cr.queries), 1)
        self.assertTrue(cr.queries[0].lstrip().upper().startswith('SELECT'))

    # UC-V6
    def test_single_minimum_not_above_the_kit(self):
        kit_version = get_manifest(KIT)['version']
        self.assertLessEqual(parse_version(PK_MIN_VERSION), parse_version(kit_version))
        self.assertGreaterEqual(parse_version(PK_MIN_VERSION), parse_version('19.0.1.14.0'))
