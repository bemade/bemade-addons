"""Task 1597 (portal app P3): the event form filters the teams by
organization, and an event never mixes the teams of two organizations.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Server refusal (create AND edit): an event whose teams belong to more
  than one organization is refused by the model, with a clear, translated
  message naming the organizations — whatever the path (ORM, the shell's
  create form, the event page's pencil card, the legacy save route).
* UC-2 What stays allowed: the teams of ONE organization, a team without
  organization alone, and one organization's teams plus teams without
  organization (the rule only ever compared the teams that HAVE one).
* UC-3 The form: an Organization select (« All organizations » + the
  organizations of the offered teams) above the team checkboxes; every
  team checkbox carries its organization (``data-sc-org-id``, empty for a
  team without one). Task 1608: the checkboxes became the tags field, whose
  options carry the organization (group key).
* UC-4 Default organization from context: the posted one after a refusal
  (flash), ``?organization_id=`` (the events list passes its organization
  filter to « New event »), the selected teams' single organization, or the
  only organization when every offered team belongs to it; none when the
  user's teams span several organizations. An organization the user has no
  team in is ignored.
* UC-5 Tour: picking an organization narrows the team list to its teams and
  unticks the teams of the other organizations; the event is created with
  the remaining team only.
* UC-6 French (fr_CA): the refusal message and the form's new labels.
"""
import json
from datetime import datetime, timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

START = datetime(2026, 5, 4, 18, 0)


class Org1597Common(Parity1577Common):
    """PC Org (teams A, B, AA Unstaffed) + a second organization with one
    team + a team without organization."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.org2 = env['res.partner'].create({'name': 'ZZ Org 1597', 'is_company': True})
        cls.team_c = env['sports.team'].create({'name': 'ZZ Team C 1597', 'parent_id': cls.org2.id})
        cls.team_free = env['sports.team'].create({'name': 'ZZ Free Team 1597'})

    def _vals(self, teams, **extra):
        return dict({
            'name': 'SC 1597 Event', 'event_type': 'game',
            'team_ids': [Command.set(teams.ids)],
            'date_start': START, 'date_end': START + timedelta(hours=2),
        }, **extra)

    def _staff_tp_on(self, *teams):
        for team in teams:
            self.env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})

    def _form(self, url='/my/event/create'):
        _text, tree = self._get(url)
        return tree.xpath('//form[@data-sc-event-form]')[0]

    @staticmethod
    def _selected_org(form):
        return form.xpath('.//select[@name="organization_id"]/option[@selected]/@value')


@tagged('post_install', '-at_install')
class TestEventOrgTeamFilter1597(Org1597Common):

    # -- UC-1 ------------------------------------------------------------
    def test_model_refuses_mixed_orgs_on_create(self):
        with self.assertRaises(ValidationError) as cm:
            self.env['sports.event'].create(self._vals(self.team_a | self.team_c))
        self.assertIn('same organization', str(cm.exception))
        self.assertIn('PC Org', str(cm.exception))
        self.assertIn('ZZ Org 1597', str(cm.exception))

    def test_model_refuses_mixed_orgs_on_edit(self):
        with self.assertRaises(ValidationError):
            self.event.write({'team_ids': [Command.link(self.team_c.id)]})

    @mute_logger('odoo.http')
    def test_shell_create_refused_and_form_keeps_input(self):
        self._switch(True)
        self._login_cadmin()
        resp = self._post('/my/event/create/submit', {
            'name': 'SC 1597 Mixed', 'event_type': 'game', 'organization_id': '',
            'team_ids': '%s,%s' % (self.team_a.id, self.team_c.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].endswith('/my/event/create'))
        self.assertFalse(self.env['sports.event'].search([('name', '=', 'SC 1597 Mixed')]))
        text, tree = self._get('/my/event/create')
        self.assertIn('same organization', text)
        # Task 1608 (deliberate update): the teams field (tags, form mode)
        # holds them, and the hidden CSV field the form posts.
        checked = tree.xpath('//form[@data-sc-event-form]//input[@name="team_ids"]/@value')[0].split(',')
        self.assertEqual(set(checked), {str(self.team_a.id), str(self.team_c.id)})

    @mute_logger('odoo.http')
    def test_pencil_edit_refused(self):
        self._switch(True)
        self._staff_tp_on(self.team_c)
        self._login_tp()
        self.event.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.event/%s' % self.event.id, data={
            'field': 'team_ids', 'value': '%s,%s' % (self.team_a.id, self.team_c.id),
            'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(self.event.write_date)}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn('same organization', resp.json()['message'])
        self.event.invalidate_recordset()
        self.assertEqual(self.event.team_ids, self.team_a)

    @mute_logger('odoo.http')
    def test_legacy_save_refused(self):
        self._staff_tp_on(self.team_c)
        self._login_tp()
        resp = self._post('/my/event/%s/save' % self.event.id, {
            'name': self.event.name, 'team_ids': '%s,%s' % (self.team_a.id, self.team_c.id),
            'assigned_staff_ids': str(self.tp.id)})
        self.assertIn('/edit?error=', resp.headers['Location'])
        self.event.invalidate_recordset()
        self.assertEqual(self.event.team_ids, self.team_a)

    # -- UC-2 ------------------------------------------------------------
    def test_allowed_combinations(self):
        Event = self.env['sports.event']
        one_org = Event.create(self._vals(self.team_a | self.team_b))
        self.assertEqual(one_org.partner_id, self.org)
        free = Event.create(self._vals(self.team_free))
        self.assertFalse(free.partner_id)
        org_and_free = Event.create(self._vals(self.team_c | self.team_free))
        self.assertEqual(org_and_free.partner_id, self.org2)

    def test_shell_create_single_org(self):
        self._switch(True)
        self._login_cadmin()
        resp = self._post('/my/event/create/submit', {
            'name': 'SC 1597 Single', 'event_type': 'game', 'organization_id': str(self.org2.id),
            'team_ids': str(self.team_c.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertEqual(resp.status_code, 303)
        event = self.env['sports.event'].search([('name', '=', 'SC 1597 Single')])
        self.assertEqual(event.team_ids, self.team_c)
        self.assertEqual(event.partner_id, self.org2)

    def test_portal_tp_creates_event_for_team_without_org(self):
        self._switch(True)
        self._staff_tp_on(self.team_free)
        self._login_tp()
        resp = self._post('/my/event/create/submit', {
            'name': 'SC 1597 Free', 'event_type': 'practice', 'organization_id': '',
            'team_ids': str(self.team_free.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertEqual(resp.status_code, 303)
        self.assertIn('created=1', resp.headers['Location'])
        event = self.env['sports.event'].search([('name', '=', 'SC 1597 Free')])
        self.assertEqual(event.team_ids, self.team_free)

    # -- UC-3 ------------------------------------------------------------
    def test_form_has_org_select_and_team_orgs(self):
        self._switch(True)
        self._login_cadmin()
        form = self._form()
        select = form.xpath('.//select[@name="organization_id"][@data-sc-org-select]')
        self.assertEqual(len(select), 1)
        values = select[0].xpath('./option/@value')
        self.assertEqual(values[0], '')
        self.assertIn(str(self.org.id), values)
        self.assertIn(str(self.org2.id), values)
        # Task 1608 (deliberate update): every team option of the tags field
        # carries its organization (group key; '' for a team without one).
        teams_card = form.xpath('.//*[@data-sc-section="event.form.teams"]')[0]
        props = json.loads(teams_card.xpath('.//owl-component/@props')[0])
        orgs = {opt[0]: opt[3] for opt in props['options']}
        self.assertEqual(orgs[str(self.team_a.id)], str(self.org.id))
        self.assertEqual(orgs[str(self.team_c.id)], str(self.org2.id))
        self.assertEqual(orgs[str(self.team_free.id)], '')
        # The select sits in the teams card, above the field, and narrows it.
        self.assertTrue(teams_card.xpath('.//select[@data-sc-org-select]'))
        self.assertEqual(props['groupSelect'], teams_card.xpath('.//select[@data-sc-org-select]/@id')[0])

    # -- UC-4 ------------------------------------------------------------
    def test_default_org_single_org_user(self):
        # Review fixes 2026-10-18 b: every team is offered, so the form opens
        # on an organization only when every team belongs to that one.
        self._switch(True)
        self._login_tp()  # staffs PC Team A only
        self.assertEqual(self._selected_org(self._form()), [])
        self.env['sports.team'].search([]).write({'parent_id': self.org.id})
        self.assertEqual(self._selected_org(self._form()), [str(self.org.id)])

    def test_no_default_org_when_teams_span_orgs(self):
        self._switch(True)
        self._login_cadmin()
        self.assertEqual(self._selected_org(self._form()), [])

    def test_no_default_org_when_a_team_has_none(self):
        # One organization, but a team without one is also offered: picking
        # the organization would hide it.
        self._switch(True)
        self._staff_tp_on(self.team_free)
        self._login_tp()
        self.assertEqual(self._selected_org(self._form()), [])

    def test_default_org_from_query(self):
        self._switch(True)
        self._login_cadmin()
        form = self._form('/my/event/create?organization_id=%s' % self.org2.id)
        self.assertEqual(self._selected_org(form), [str(self.org2.id)])
        # An organization none of the offered teams belongs to is ignored.
        stranger = self.env['res.partner'].create({'name': 'Stranger Org 1597', 'is_company': True})
        form = self._form('/my/event/create?organization_id=%s' % stranger.id)
        self.assertEqual(self._selected_org(form), [])
        form = self._form('/my/event/create?organization_id=abc')
        self.assertEqual(self._selected_org(form), [])

    @mute_logger('odoo.http')
    def test_default_org_from_flash(self):
        self._switch(True)
        self._login_cadmin()
        self._post('/my/event/create/submit', {
            'name': '', 'organization_id': str(self.org2.id), 'team_ids': str(self.team_c.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertEqual(self._selected_org(self._form()), [str(self.org2.id)])

    @mute_logger('odoo.http')
    def test_default_org_from_flashed_teams(self):
        self._switch(True)
        self._login_cadmin()
        self._post('/my/event/create/submit', {
            'name': '', 'team_ids': str(self.team_c.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertEqual(self._selected_org(self._form()), [str(self.org2.id)])

    def test_events_list_passes_its_org_filter(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/events?no_default_dates=1&organization_id=%s' % self.org.id)
        # Task 1607 (deliberate update): « + Ajouter » is in the list header.
        self.assertEqual(tree.xpath('//div[contains(@class, "o_sc_list_header")]//a[@data-sc-action="events.create"]/@href'),
                         ['/my/event/create?organization_id=%s' % self.org.id])


@tagged('post_install', '-at_install')
class TestEventOrgTeamFilterTour1597(Org1597Common):

    def test_pick_org_narrows_teams(self):
        self._switch(True)
        self.start_tour('/my/event/create', 'sc_1597_event_org_filter', login='p77.cadmin@example.com')
        event = self.env['sports.event'].search([('name', '=', 'SC 1597 Tour')])
        self.assertEqual(event.team_ids, self.team_c)
        self.assertEqual(event.partner_id, self.org2)


@tagged('post_install', '-at_install')
class TestEventOrgTeamFilterI18n1597(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org2 = cls.env['res.partner'].create({'name': 'ZZ Org 1597', 'is_company': True})
        cls.team_c = cls.env['sports.team'].create({'name': 'ZZ Team C 1597', 'parent_id': cls.org2.id})

    def test_refusal_in_french(self):
        env_fr = self.env(context=dict(self.env.context, lang='fr_CA'))
        with self.assertRaises(ValidationError) as cm:
            env_fr['sports.event'].create({
                'name': 'SC 1597 FR', 'team_ids': [Command.set((self.team_a | self.team_c).ids)],
                'date_start': START, 'date_end': START + timedelta(hours=2)})
        self.assertIn('doivent toutes appartenir à la même organisation', str(cm.exception))
        with self.assertRaises(ValidationError) as cm:
            env_fr['sports.event'].create({
                'name': 'SC 1597 FR', 'team_ids': [Command.clear()],
                'date_start': START, 'date_end': START + timedelta(hours=2)})
        self.assertEqual(str(cm.exception), "Veuillez choisir au moins une équipe pour l'événement.")

    def test_form_in_french(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/event/create'))
        select = tree.xpath('//select[@data-sc-org-select]')[0]
        self.assertEqual(select.xpath('./option[1]')[0].text_content().strip(), 'Toutes les organisations')
        label = tree.xpath('//label[@for="sc_event_org"]')[0].text_content().strip()
        self.assertEqual(label, 'Organisation')
