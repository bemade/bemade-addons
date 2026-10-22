"""Use case: "show as free" survives the Odoo <-> CalDAV round trip.

Calendar clients mark an event free with iCalendar TRANSP:TRANSPARENT; Odoo with
``calendar.event.show_as = 'free'`` ("Available"), which the Appointments app and
the attendee availability check both honour. Before this, caldav_sync neither
read nor wrote TRANSP: every imported event came in busy, and marking an event
available in Odoo never reached the server. The mapping is base_caldav's.

Import (server -> Odoo)
    AC1  A polled event with TRANSP:TRANSPARENT is created with show_as 'free';
         TRANSP:OPAQUE or no TRANSP gives 'busy'.
    AC2  When an already-imported event's TRANSP changes on the server, the next
         poll updates show_as accordingly.

Push (Odoo -> server)
    AC3  An event created in Odoo with show_as 'free' is pushed with
         TRANSP:TRANSPARENT; with 'busy', TRANSP:OPAQUE.
    AC4  Changing only show_as on a synced event pushes the update carrying the
         new TRANSP.

Refactor guard (no new test): caldav_sync's existing suite passes unchanged on
top of base_caldav -- same res.users field names, ``_get_caldav_client`` and
``_get_caldav_events`` kept, ``caldav.DAVClient`` still patchable.
UAT on staging: upgrading caldav_sync installs base_caldav, and existing users
keep their CalDAV credentials and is_caldav_enabled.
"""

from odoo.tests import TransactionCase, tagged

from .common import CaldavTestCommon


@tagged("post_install", "-at_install")
class TestTranspShowAs(TransactionCase, CaldavTestCommon):
    def test_import_transp_sets_show_as(self):
        """AC1"""
        self.skipTest("TDD: not written yet")

    def test_import_transp_change_updates_show_as(self):
        """AC2"""
        self.skipTest("TDD: not written yet")

    def test_push_show_as_sets_transp(self):
        """AC3"""
        self.skipTest("TDD: not written yet")

    def test_show_as_only_write_is_pushed(self):
        """AC4"""
        self.skipTest("TDD: not written yet")
