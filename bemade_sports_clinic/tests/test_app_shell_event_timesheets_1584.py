"""Task 1584 — event page timesheets: clinic admins see all, the therapist's
name on each row, a neutral title, a labelled missing banner. Synthetic
fixtures only.

Acceptance criteria:

* UC-1 A clinic administrator (NOT assigned to the event) sees every
  therapist's timesheet on the event page, each row naming its therapist,
  under « Timesheets » (« Feuilles de temps »), and the missing-timesheet
  banner is labelled « Missing timesheets: » (« Feuilles de temps
  manquantes : ») followed by the names.
* UC-2 A system administrator gets the same full view.
* UC-3 An assigned therapist still sees ONLY their own timesheet, without a
  name (it's theirs), under « My Timesheets » (« Mes feuilles de temps »),
  and no missing banner.
* UC-4 A coach sees no timesheet section at all.
* UC-5 Switch OFF: the legacy event page follows the same flag — a clinic
  admin sees every therapist's row in the legacy table.
* UC-6 /my/sc/timesheets (own rows only) shows no therapist name.
* UC-7 In a browser (phone width), the clinic admin's event page shows both
  named cards, read-only, and the labelled banner
  (static/tests/tours/sc_app_event_timesheets_tours.js).
* UC-8 fr_CA (website-aware): « Feuilles de temps », « Mes feuilles de
  temps », « Feuilles de temps manquantes : ».
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class EventTimesheets1584Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'SC84 Second Therapist', 'login': 'sc84.tp2@example.com',
            'password': 'sc84-tp2-pass',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist',
        })
        # Assigned: tp (has a timesheet), tp2 (has one), itp (missing one).
        cls.event.write({'assigned_staff_ids': [Command.link(cls.tp2.id), Command.link(cls.itp.id)]})
        cls.ts_tp2 = env['sports.event.timesheet'].create({
            'event_id': cls.event.id, 'user_id': cls.tp2.id,
        })
        cls.sysadmin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'SC84 System Admin', 'login': 'sc84.sys@example.com',
            'password': 'sc84-sys-pass',
            # An internal therapist (so the app shell applies) who is NOT a
            # clinic admin and NOT assigned: only base.group_system widens.
            'group_ids': [Command.set([
                env.ref('base.group_user').id, env.ref('base.group_system').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id])],
        })

    def _section(self, tree):
        nodes = tree.xpath('//*[@data-sc-section="event.timesheets"]')
        return nodes[0] if nodes else None

    def _title(self, section):
        return ' '.join(' '.join(section.xpath('.//h2[contains(@class, "o_sc_section_header")]//text()')).split())

    def _cards(self, section):
        return {int(card.get('data-sc-timesheet-id')): card
                for card in section.xpath('.//*[@data-sc-timesheet-id]')}

    def _employee(self, card):
        return ' '.join(card.xpath('.//*[@data-sc-timesheet-employee]//text()')).strip()

    def _missing_text(self, section):
        banner = section.xpath('.//*[@data-sc-missing-timesheets]')
        self.assertTrue(banner)
        return ' '.join(' '.join(banner[0].xpath('.//text()')).split())


@tagged('post_install', '-at_install')
class TestAppShellEventTimesheets1584(EventTimesheets1584Common):

    def _assert_full_view(self):
        _text, tree = self._get('/my/event/%s' % self.event.id)
        section = self._section(tree)
        self.assertIsNotNone(section)
        self.assertEqual(self._title(section), 'Timesheets')
        cards = self._cards(section)
        self.assertEqual(set(cards), {self.timesheet.id, self.ts_tp2.id})
        self.assertEqual(self._employee(cards[self.timesheet.id]), 'PC TP')
        self.assertEqual(self._employee(cards[self.ts_tp2.id]), 'SC84 Second Therapist')
        # Not theirs: read-only (no pencil) for the admin.
        self.assertFalse(section.xpath('.//*[@data-sc-edit-card]'))
        self.assertEqual(self._missing_text(section), 'Missing timesheets: P77 Internal TP')

    # -- UC-1 ------------------------------------------------------------
    def test_clinic_admin_sees_all_with_names(self):
        self._switch(True)
        self.assertNotIn(self.cadmin, self.event.assigned_staff_ids)
        self._login_cadmin()
        self._assert_full_view()

    # -- UC-2 ------------------------------------------------------------
    def test_system_admin_sees_all_with_names(self):
        self._switch(True)
        self.authenticate('sc84.sys@example.com', 'sc84-sys-pass')
        self._assert_full_view()

    # -- UC-3 ------------------------------------------------------------
    def test_assigned_tp_sees_own_only(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        section = self._section(tree)
        self.assertEqual(self._title(section), 'My Timesheets')
        cards = self._cards(section)
        self.assertEqual(set(cards), {self.timesheet.id})
        self.assertEqual(self._employee(cards[self.timesheet.id]), '')
        self.assertFalse(section.xpath('.//*[@data-sc-missing-timesheets]'))

    # -- UC-4 ------------------------------------------------------------
    def test_coach_sees_nothing(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        self.assertIsNone(self._section(tree))
        self.assertFalse(tree.xpath('//*[@data-sc-timesheet-id]'))

    # -- UC-5 ------------------------------------------------------------
    def test_legacy_clinic_admin_sees_all(self):
        self._switch(False)
        self._login_cadmin()
        text, tree = self._get('/my/event/%s' % self.event.id)
        self.assertIsNone(self._shell(tree))
        self.assertIn('<span>PC TP</span>', text)
        self.assertIn('<span>SC84 Second Therapist</span>', text)

    # -- UC-6 ------------------------------------------------------------
    def test_own_timesheets_list_has_no_name(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        self.assertTrue(tree.xpath('//*[@data-sc-timesheet-id="%s"]' % self.timesheet.id))
        self.assertFalse(tree.xpath('//*[@data-sc-timesheet-employee]'))


@tagged('post_install', '-at_install')
class TestAppShellEventTimesheetsTourPhone1584(EventTimesheets1584Common):
    """UC-7 in a browser (static/tests/tours/sc_app_event_timesheets_tours.js)."""
    browser_size = '390x844'

    def test_clinic_admin_event_timesheets(self):
        self._switch(True)
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1584_event_timesheets_admin',
                        login='p77.cadmin@example.com')


@tagged('post_install', '-at_install')
class TestAppShellEventTimesheetsFr1584(EventTimesheets1584Common):
    """UC-8: rendered in fr_CA (website-aware: fr_CA on the website + the
    frontend_lang cookie)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        (cls.tp | cls.cadmin).write({'lang': 'fr_CA'})

    def _fr_section(self):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/event/%s' % self.event.id)
        return self._section(tree)

    def test_admin_in_french(self):
        self._switch(True)
        self._login_cadmin()
        section = self._fr_section()
        self.assertEqual(self._title(section), 'Feuilles de temps')
        self.assertEqual(self._missing_text(section),
                         'Feuilles de temps manquantes : P77 Internal TP')

    def test_therapist_in_french(self):
        self._switch(True)
        self._login_tp()
        self.assertEqual(self._title(self._fr_section()), 'Mes feuilles de temps')
