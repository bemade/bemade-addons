"""Task 1608 (portal app): the event form's teams and « Assigned Staff » are
the compact multi-select (tags field) with a browse-all list, and the
coverage times follow the event times as in the legacy portal. Synthetic
fixtures only (this repository is public).

Acceptance criteria covered here:

* UC-1 The create form: teams and assigned staff are FORM-mode tags fields
  (no checkbox list left) writing the CSV hidden inputs the routes accept
  (``team_ids``, ``assigned_staff_ids``, prefilled with the offered ids
  only); the teams field is narrowed by the organization select
  (``groupSelect``).
* UC-2 Full visibility (owner decision 2026-10-17): EVERY offered team and
  therapist is in the field's options (no cap) — a clinic administrator gets
  every team; teams carry their organization (grouped, by organization
  name, « No organization » last, name order inside a group).
* UC-3 Submit: the CSV fields create the event with those teams and that
  staff; a refused input (mixed organizations, task 1597) comes back
  prefilled in the fields' values.
* UC-4 The event page's teams field carries the same groups (the browse
  list), its save unchanged.
* UC-5 Coverage snapping on the event page (autosave): a new start sets the
  coverage start to it, the end to start + 2 h and the coverage end to that
  end, answered under « also »; a new end sets the coverage end to it when
  it was empty or earlier, never when later; a coverage time saved alone
  moves nothing else.
* UC-6 Tours: create an event picking from the full list without typing
  (teams grouped by organization, staff) and by typing; a new start moves
  the end / coverage times, a new end the coverage end; the organization
  select narrows the list (task 1597 tour, updated). On the event page a
  new start moves the card's fields.
* UC-7 French (fr_CA): « No organization », the fields' labels and
  placeholders.
"""
import json
from datetime import datetime, timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_event_org_team_filter_1597 import Org1597Common


def _props(node):
    return json.loads(node.get('props'))


class Pickers1608Common(Org1597Common):

    def _pickers(self, form):
        """{'teams': props, 'staff': props} of the form's tags fields."""
        out = {}
        for key in ('teams', 'staff'):
            nodes = form.xpath('.//*[@data-sc-event-pick="%s"]//owl-component' % key)
            self.assertEqual(len(nodes), 1, key)
            out[key] = _props(nodes[0])
        return out

    def _hidden(self, form, name):
        return form.xpath('.//input[@type="hidden"][@name="%s"]/@value' % name)[0]

    def _event_props(self, field):
        _text, tree = self._get('/my/event/%s' % self.event.id)
        for node in tree.xpath('//owl-component[@props]'):
            props = _props(node)
            if props.get('field') == field and props.get('model') == 'sports.event':
                return props
        self.fail('no %s field on the event page' % field)


@tagged('post_install', '-at_install')
class TestEventFormPickers1608(Pickers1608Common):

    # -- UC-1 ------------------------------------------------------------
    def test_form_uses_tags_fields_in_form_mode(self):
        self._switch(True)
        self._login_cadmin()
        form = self._form()
        self.assertFalse(form.xpath('.//input[@type="checkbox"]'), "no checkbox list left")
        pickers = self._pickers(form)
        teams, staff = pickers['teams'], pickers['staff']
        for props, target in ((teams, 'sc_event_team_ids'), (staff, 'sc_event_staff_ids')):
            self.assertEqual(props['mode'], 'form')
            self.assertEqual(props['inputType'], 'tags')
            self.assertEqual(props['target'], target)
            self.assertTrue(form.xpath('.//input[@type="hidden"][@id="%s"]' % target), target)
        self.assertEqual(form.xpath('.//input[@id="sc_event_team_ids"]/@name'), ['team_ids'])
        self.assertEqual(form.xpath('.//input[@id="sc_event_staff_ids"]/@name'), ['assigned_staff_ids'])
        # The organization select narrows the teams (task 1597), not the staff.
        self.assertEqual(teams['groupSelect'], 'sc_event_org')
        self.assertTrue(form.xpath('.//select[@id="sc_event_org"][@data-sc-org-select]'))
        self.assertNotIn('groupSelect', staff)
        self.assertEqual(form.get('data-sc-event-form-mode'), 'create')

    def test_no_group_select_without_organizations(self):
        self.env['sports.team'].search([]).write({'parent_id': False})
        self._switch(True)
        self._login_tp()
        form = self._form()
        self.assertFalse(form.xpath('.//select[@data-sc-org-select]'))
        self.assertNotIn('groupSelect', self._pickers(form)['teams'])

    # -- UC-2 ------------------------------------------------------------
    def test_every_team_and_therapist_offered_grouped(self):
        # More teams than the old 8-suggestion cap: all of them are offered.
        extra = self.env['sports.team'].create([
            {'name': 'ZZ Bulk %02d 1608' % i, 'parent_id': self.org2.id} for i in range(12)])
        self._switch(True)
        self._login_cadmin()
        pickers = self._pickers(self._form())
        options = pickers['teams']['options']
        keys = [opt[0] for opt in options]
        for team in self.team_a | self.team_b | self.team_c | self.team_free | extra:
            self.assertIn(str(team.id), keys, team.name)
        self.assertEqual(len(keys), self.env['sports.team'].search_count([]))
        by_key = {opt[0]: opt for opt in options}
        self.assertEqual(by_key[str(self.team_a.id)][2:], ['PC Org', str(self.org.id)])
        self.assertEqual(by_key[str(self.team_c.id)][2:], ['ZZ Org 1597', str(self.org2.id)])
        self.assertEqual(by_key[str(self.team_free.id)][2:], ['No organization', ''])
        # Grouped: by organization name, « No organization » last, names inside.
        groups = [opt[2] for opt in options]
        org_groups = [g for g in groups if g != 'No organization']
        self.assertEqual(org_groups, sorted(org_groups, key=str.lower))
        self.assertEqual(groups[-1], 'No organization')
        pc = [opt[1] for opt in options if opt[2] == 'PC Org']
        self.assertEqual(pc, sorted(pc, key=str.lower))
        # Every therapist.
        staff_keys = [opt[0] for opt in pickers['staff']['options']]
        self.assertIn(str(self.tp.id), staff_keys)
        self.assertGreaterEqual(len(staff_keys), 1)

    def test_tp_offered_every_team(self):
        # Review fixes 2026-10-18 b (owner decision): every team for every
        # user who may create events (was: the teams they staff).
        self._switch(True)
        self._login_tp()  # staffs PC Team A only
        keys = [opt[0] for opt in self._pickers(self._form())['teams']['options']]
        self.assertEqual(sorted(keys), sorted(str(i) for i in self.env['sports.team'].search([]).ids))

    # -- UC-3 ------------------------------------------------------------
    def test_submit_csv_creates_event(self):
        self._switch(True)
        self._login_cadmin()
        resp = self._post('/my/event/create/submit', {
            'name': 'SC 1608 Created', 'event_type': 'game', 'organization_id': str(self.org.id),
            'team_ids': '%s,%s' % (self.team_a.id, self.team_b.id),
            'assigned_staff_ids': str(self.tp.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
            'therapist_start': '2026-05-04T18:00', 'therapist_end': '2026-05-04T20:00',
        })
        self.assertEqual(resp.status_code, 303)
        event = self.env['sports.event'].search([('name', '=', 'SC 1608 Created')])
        self.assertEqual(event.team_ids, self.team_a | self.team_b)
        self.assertEqual(event.assigned_staff_ids, self.tp)

    @mute_logger('odoo.http')
    def test_refused_input_comes_back_in_the_fields(self):
        self._switch(True)
        self._login_cadmin()
        self._post('/my/event/create/submit', {
            'name': 'SC 1608 Mixed', 'event_type': 'game', 'organization_id': '',
            'team_ids': '%s,%s' % (self.team_a.id, self.team_c.id),
            'assigned_staff_ids': str(self.tp.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        self.assertFalse(self.env['sports.event'].search([('name', '=', 'SC 1608 Mixed')]))
        text, tree = self._get('/my/event/create')
        self.assertIn('same organization', text)
        form = tree.xpath('//form[@data-sc-event-form]')[0]
        pickers = self._pickers(form)
        self.assertEqual(set(pickers['teams']['value'].split(',')), {str(self.team_a.id), str(self.team_c.id)})
        self.assertEqual(set(self._hidden(form, 'team_ids').split(',')), {str(self.team_a.id), str(self.team_c.id)})
        self.assertEqual(pickers['staff']['value'], str(self.tp.id))
        self.assertEqual(self._hidden(form, 'assigned_staff_ids'), str(self.tp.id))

    @mute_logger('odoo.http')
    def test_unoffered_ids_are_not_prefilled(self):
        # A flashed id that is not offered (review fixes 2026-10-18 b: every
        # team is offered now, so an unknown one) is dropped, as the checkbox
        # list did.
        self._switch(True)
        self._login_tp()
        self._post('/my/event/create/submit', {
            'name': '', 'team_ids': '%s,999999' % self.team_a.id,
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
        })
        form = self._form()
        self.assertEqual(self._hidden(form, 'team_ids'), str(self.team_a.id))

    # -- UC-4 ------------------------------------------------------------
    def test_event_page_teams_grouped(self):
        self._switch(True)
        self._login_cadmin()
        props = self._event_props('team_ids')
        self.assertEqual(props['inputType'], 'tags')
        by_key = {opt[0]: opt for opt in props['options']}
        self.assertEqual(by_key[str(self.team_a.id)][2:], ['PC Org', str(self.org.id)])
        self.assertEqual(by_key[str(self.team_free.id)][2], 'No organization')
        staff = self._event_props('assigned_staff_ids')
        self.assertIn(str(self.tp.id), [opt[0] for opt in staff['options']])

    # -- UC-5 ------------------------------------------------------------
    def _save(self, field, value):
        self.event.invalidate_recordset()
        return self.url_open('/my/app/save/sports.event/%s' % self.event.id, data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(self.event.sudo().write_date),
        }, allow_redirects=False)

    def _local(self, field):
        self.event.invalidate_recordset()
        value = self.event.sudo()[field]
        return fields.Datetime.context_timestamp(
            self.event.with_user(self.tp), value).strftime('%Y-%m-%dT%H:%M') if value else ''

    def test_start_save_cascades(self):
        self._switch(True)
        self._login_tp()
        resp = self._save('date_start', '2026-03-05T17:30')
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(self._local('date_start'), '2026-03-05T17:30')
        self.assertEqual(self._local('therapist_start'), '2026-03-05T17:30')
        self.assertEqual(self._local('date_end'), '2026-03-05T19:30')
        self.assertEqual(self._local('therapist_end'), '2026-03-05T19:30')
        self.assertEqual(set(payload['also']), {'therapist_start', 'date_end', 'therapist_end'})
        self.assertEqual(payload['also']['date_end']['value'], '2026-03-05T19:30')
        self.assertEqual(payload['also']['therapist_start']['value'], '2026-03-05T17:30')
        self.assertEqual(payload['also']['therapist_end']['value'], '2026-03-05T19:30')
        self.assertTrue(payload['also']['date_end']['display'])

    def test_end_save_moves_coverage_end_when_empty_or_earlier(self):
        self._switch(True)
        self._login_tp()
        self.event.sudo().write({'therapist_end': False})
        resp = self._save('date_end', '2026-02-02T13:00')  # local
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._local('therapist_end'), '2026-02-02T13:00')
        self.assertEqual(resp.json()['also']['therapist_end']['value'], '2026-02-02T13:00')
        # Earlier → moved to the new end.
        resp = self._save('date_end', '2026-02-02T14:00')
        self.assertEqual(self._local('therapist_end'), '2026-02-02T14:00')
        self.assertIn('therapist_end', resp.json()['also'])
        # Later → kept, nothing else answered.
        resp = self._save('date_end', '2026-02-02T13:30')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._local('therapist_end'), '2026-02-02T14:00')
        self.assertNotIn('also', resp.json())

    def test_coverage_saved_alone_moves_nothing(self):
        self._switch(True)
        self._login_tp()
        start, end = self._local('date_start'), self._local('date_end')
        resp = self._save('therapist_start', '2026-02-02T09:00')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn('also', resp.json())
        self.assertEqual((self._local('date_start'), self._local('date_end')), (start, end))


@tagged('post_install', '-at_install')
class TestEventFormPickers1608I18n(Pickers1608Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.cadmin.write({'lang': 'fr_CA'})

    def test_form_in_french(self):
        self._switch(True)
        self._login_cadmin()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/event/create')
        pickers = self._pickers(tree.xpath('//form[@data-sc-event-form]')[0])
        self.assertEqual(pickers['teams']['label'], 'Équipes')
        self.assertEqual(pickers['teams']['placeholder'], 'Ajouter une équipe…')
        self.assertEqual(pickers['staff']['label'], 'Personnel assigné')
        self.assertEqual(pickers['staff']['placeholder'], 'Ajouter un thérapeute…')
        groups = {opt[2] for opt in pickers['teams']['options']}
        self.assertIn('Aucune organisation', groups)


@tagged('post_install', '-at_install')
class TestEventFormPickersTour1608(Pickers1608Common):

    def test_create_by_browsing_and_typing(self):
        self._switch(True)
        self.start_tour('/my/event/create', 'sc_1608_event_form_pickers', login='p77.cadmin@example.com')
        event = self.env['sports.event'].search([('name', '=', 'SC 1608 Tour')])
        self.assertEqual(event.team_ids, self.team_a | self.team_b)
        self.assertIn(self.tp, event.assigned_staff_ids)
        local = lambda value: fields.Datetime.context_timestamp(  # noqa: E731
            event.with_user(self.cadmin), value).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(local(event.date_start), '2026-05-04T18:00')
        self.assertEqual(local(event.therapist_start), '2026-05-04T18:00')
        self.assertEqual(local(event.date_end), '2026-05-04T21:00')
        self.assertEqual(local(event.therapist_end), '2026-05-04T21:00')

    def test_event_page_start_moves_the_card(self):
        self._switch(True)
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1608_event_page_snap', login='pc.tp@example.com')
        self.event.invalidate_recordset()
        local = lambda value: fields.Datetime.context_timestamp(  # noqa: E731
            self.event.with_user(self.tp), value).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(local(self.event.date_start), '2026-03-05T17:30')
        self.assertEqual(local(self.event.date_end), '2026-03-05T19:30')
        self.assertEqual(local(self.event.therapist_start), '2026-03-05T17:30')
        self.assertEqual(local(self.event.therapist_end), '2026-03-05T19:30')
