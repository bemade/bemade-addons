"""Task 1237 — show assigned Treatment Professionals on the backend calendar.

Acceptance:
 * Each backend Sports-Events calendar tile shows the event name followed by the
   assigned TPs' initials in brackets ("Practice A (MC JD)"), and just the name
   (no empty "()") when unassigned — driven by a non-stored computed
   ``calendar_label`` char surfaced via the ``create_name_field`` calendar arch
   attribute. No JS.
 * The calendar popover shows the assigned TP (``assigned_staff_ids`` in the
   calendar arch) and the TP can be set/changed inline through the calendar
   popup form (``sports_event_view_form_calendar_popup``), and it persists.
 * A calendar drag/resize (which the web client couples with a write of the
   ``create_name_field`` value) must not break and the label recomputes.
"""

from datetime import datetime

from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCovCalendarLabel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({'name': 'CL Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create({'name': 'CL Team', 'parent_id': cls.org.id})

        tp_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        base_user = cls.env.ref('base.group_user')

        def _mk(name, login):
            return cls.env['res.users'].create({
                'name': name, 'login': login, 'email': f'{login}@example.com',
                'group_ids': [Command.link(base_user.id), Command.link(tp_group.id)],
            })

        cls.tp_mc = _mk('Marie Curie', 'cl_tp_mc')
        cls.tp_jd = _mk('John Doe', 'cl_tp_jd')

    def _event(self, **vals):
        vals.setdefault('name', 'Practice A')
        vals.setdefault('team_ids', [Command.set([self.team.id])])
        vals.setdefault('date_start', datetime(2026, 1, 5, 10, 0))
        vals.setdefault('date_end', datetime(2026, 1, 5, 12, 0))
        return self.env['sports.event'].create(vals)

    # ----- calendar_label compute -----

    def test_label_no_staff_is_name_only(self):
        """Unassigned event: label is just the name, no empty brackets."""
        ev = self._event()
        self.assertEqual(ev.calendar_label, 'Practice A')
        self.assertNotIn('(', ev.calendar_label)

    def test_label_single_staff(self):
        ev = self._event(assigned_staff_ids=[Command.set([self.tp_mc.id])])
        self.assertEqual(ev.calendar_label, 'Practice A (MC)')

    def test_label_multiple_staff_space_joined(self):
        ev = self._event(assigned_staff_ids=[Command.set([self.tp_mc.id, self.tp_jd.id])])
        self.assertEqual(ev.calendar_label, 'Practice A (MC JD)')

    def test_label_orders_head_therapist_first(self):
        """Initials ordered: head therapist, then other TPs, then non-TP others."""
        tp_group = self.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        base_user = self.env.ref('base.group_user')
        head = self.env['res.users'].create({
            'name': 'Hana Kim', 'login': 'cl_head', 'email': 'cl_head@example.com',
            'group_ids': [Command.link(base_user.id), Command.link(tp_group.id)],
        })
        other = self.env['res.users'].create({
            'name': 'Zoe Other', 'login': 'cl_other', 'email': 'cl_other@example.com',
            'group_ids': [Command.link(base_user.id)],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team.id, 'partner_id': head.partner_id.id,
            'role': 'head_therapist',
        })
        # Assigned in a deliberately "wrong" order to prove the compute reorders.
        ev = self._event(assigned_staff_ids=[
            Command.set([other.id, self.tp_mc.id, head.id])])
        # head (Hana Kim=HK) -> other TP (Marie Curie=MC) -> non-TP (Zoe Other=ZO)
        self.assertEqual(ev.calendar_label, 'Practice A (HK MC ZO)')

    def test_label_recomputes_on_assignment_change(self):
        ev = self._event()
        self.assertEqual(ev.calendar_label, 'Practice A')
        ev.write({'assigned_staff_ids': [Command.link(self.tp_jd.id)]})
        self.assertEqual(ev.calendar_label, 'Practice A (JD)')
        ev.write({'assigned_staff_ids': [Command.clear()]})
        self.assertEqual(ev.calendar_label, 'Practice A')

    def test_label_recomputes_on_name_change(self):
        ev = self._event(assigned_staff_ids=[Command.set([self.tp_mc.id])])
        ev.write({'name': 'Game B'})
        self.assertEqual(ev.calendar_label, 'Game B (MC)')

    def test_label_field_not_stored(self):
        """Display-only: the field must not be persisted."""
        self.assertFalse(self.env['sports.event']._fields['calendar_label'].store)

    # ----- calendar drag/resize resilience -----

    def test_drag_write_including_label_does_not_break(self):
        """The web calendar couples a drag with a write of the create_name_field
        value (calendar_model.js buildRawRecord). Writing the readonly, non-stored
        calendar_label alongside the date fields must not raise, must leave the
        drag time-sync intact, and the label must still reflect the record."""
        ev = self._event(
            assigned_staff_ids=[Command.set([self.tp_mc.id])],
            therapist_start=datetime(2026, 1, 5, 10, 0),
            therapist_end=datetime(2026, 1, 5, 12, 0),
        )
        ev.write({
            'calendar_label': 'stale client title',
            'therapist_start': datetime(2026, 1, 5, 11, 0),
            'therapist_end': datetime(2026, 1, 5, 13, 0),
        })
        # date_* stay synced to the therapist drag
        self.assertEqual(ev.date_start, datetime(2026, 1, 5, 11, 0))
        self.assertEqual(ev.date_end, datetime(2026, 1, 5, 13, 0))
        # the stale client-sent value never persisted; label recomputes
        self.assertEqual(ev.calendar_label, 'Practice A (MC)')

    def test_create_including_label_is_ignored(self):
        """The calendar create path injects the create_name_field value into the
        payload; a calendar_label passed to create() must not stick."""
        ev = self._event(
            calendar_label='stale client title',
            assigned_staff_ids=[Command.set([self.tp_jd.id])],
        )
        self.assertEqual(ev.calendar_label, 'Practice A (JD)')

    # ----- view wiring -----

    def test_calendar_view_drives_tile_from_label(self):
        view = self.env.ref('bemade_sports_clinic.sports_event_view_calendar')
        cal = etree.fromstring(view.arch.encode()).xpath('//calendar')[0]
        self.assertEqual(
            cal.get('create_name_field'), 'calendar_label',
            "Calendar tile title must be driven by the calendar_label field.",
        )

    def test_calendar_view_exposes_assigned_staff_in_popover(self):
        view = self.env.ref('bemade_sports_clinic.sports_event_view_calendar')
        tree = etree.fromstring(view.arch.encode())
        self.assertTrue(
            tree.xpath("//calendar/field[@name='assigned_staff_ids']"),
            "assigned_staff_ids must be in the calendar arch for the popover.",
        )

    def test_calendar_popup_form_exists_with_editable_staff(self):
        """The action's form_view_ref points at this view; it must exist and
        expose assigned_staff_ids as an editable many2many_tags picker."""
        view = self.env.ref(
            'bemade_sports_clinic.sports_event_view_form_calendar_popup')
        self.assertEqual(view.model, 'sports.event')
        tree = etree.fromstring(view.arch.encode())
        staff = tree.xpath("//field[@name='assigned_staff_ids']")
        self.assertTrue(staff, "Popup form must expose assigned_staff_ids.")
        self.assertEqual(staff[0].get('widget'), 'many2many_tags')
        self.assertNotEqual(
            staff[0].get('readonly'), '1',
            "assigned_staff_ids must be editable in the calendar popup.",
        )
