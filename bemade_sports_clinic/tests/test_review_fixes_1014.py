"""Owner review fixes from the /dev-review UAT of 2026-10-14. Synthetic
fixtures only.

Acceptance criteria covered here:

* RF1 Internal-note save after a sibling save: a portal therapist saves the
  external notes, then the internal notes with the write_date loaded BEFORE
  the first save and the right ``old_value`` -> 200 (the stale-check reads the
  group-restricted field through sudo, the role allowlist having passed);
  clearing the internal notes after a sibling save -> 200 too; an injury
  WITH followers saves as well (the follower-subtype upkeep runs sudo). A
  coach still gets 403 on the internal notes, stale write_date or not.
* RF2 A cleared injury note is recorded in the history: ONE empty-content row,
  shown « Cleared » in the history sheet; the dashboards / recent changes
  still render with the note empty.
* RF3 (tours) A date typed into an autosave field is saved once, when the
  user leaves it — not on each « change » while typing; two saves in a row
  are sent one after the other (no false « changed elsewhere »).
* RF4 (see test_app_shell_player_layout) The training recommendation sits in
  the player header, above the allergies (since task 1615 right under the
  play status — test_header_order_1615).
* RF5 An activity row whose title shows its related record's name makes that
  name a link to the record (same access-gated URL as the links line), the
  title's main link carrying the whole title as its label — no nested
  anchors; a record the viewer may not open stays plain text.
* RF6 The events list / calendar, clinics and timesheets filters apply on
  change (``data-sc-autosubmit``; the « Apply filters » button kept only as
  the no-JS / Enter fallback); the group by sits in its own labelled
  « Group by » group, not among the filters (task 1607: the sort moved to
  the list header). Tour: a date applies
  once complete, a select at once, the panel stays open.
* RF8 The event end-before-start refusal (and the therapist / coverage /
  travel time-order refusals) are translated (fr_CA); on the event form the
  end-time refusal shows next to its field, not as a banner.
* RF9 The team page's « Add a player » card has ONE set of name fields: the
  « Create a new player » form carries the searched name / date of birth in
  hidden fields (enabled once a first and a last name are there).
"""
from datetime import date
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


@tagged('post_install', '-at_install')
class TestReviewFixes1014Save(AppShellCommon):

    def _wd(self, record):
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _save(self, record, field, value, write_date=None, **extra):
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value,
            'write_date': write_date or self._wd(record),
            'csrf_token': self._csrf(),
            **extra,
        }, allow_redirects=False)

    def _rows(self, scope):
        return self.env['sports.injury.note.history'].search(
            [('injury_id', '=', self.injury.id), ('scope', '=', scope)], order='id asc')

    def _follow(self):
        """Followers as a real injury has them (the team staff)."""
        self.injury.sudo().message_subscribe(
            partner_ids=(self.tp.partner_id | self.coach.partner_id).ids)

    # -- RF1 -------------------------------------------------------------
    def test_internal_notes_after_sibling_save(self):
        self.injury.sudo().write({'internal_notes': 'Synthetic internal v1'})
        self._login_tp()
        loaded = self._wd(self.injury)
        resp = self._save(self.injury, 'external_notes', 'Synthetic external', write_date=loaded)
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._save(self.injury, 'internal_notes', 'Synthetic internal v2',
                          write_date=loaded, old_value='Synthetic internal v1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.sudo().internal_notes, 'Synthetic internal v2')

    def test_internal_notes_conflict_payload_readable(self):
        """A REAL conflict on the internal notes answers 409 (not 403) with
        the current value."""
        self.injury.sudo().write({'internal_notes': 'Synthetic internal v1'})
        self._login_tp()
        resp = self._save(self.injury, 'internal_notes', 'Mine',
                          write_date='2000-01-01 00:00:00', old_value='Something else')
        self.assertEqual(resp.status_code, 409, resp.text)
        self.assertEqual(resp.json()['current_value'], 'Synthetic internal v1')

    def test_clear_internal_notes_after_sibling_save(self):
        self.injury.sudo().write({'internal_notes': 'Synthetic internal v1'})
        self._login_tp()
        loaded = self._wd(self.injury)
        resp = self._save(self.injury, 'external_notes', 'Synthetic external', write_date=loaded)
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._save(self.injury, 'internal_notes', '', write_date=loaded,
                          old_value='Synthetic internal v1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertFalse(self.injury.sudo().internal_notes)

    def test_internal_notes_with_followers(self):
        self._follow()
        self._login_tp()
        resp = self._save(self.injury, 'internal_notes', 'Synthetic followed')
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._save(self.injury, 'internal_notes', '')
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_coach_still_refused_internal_notes(self):
        self.injury.sudo().write({'internal_notes': 'Synthetic internal v1'})
        self._login_coach()
        loaded = self._wd(self.injury)
        resp = self._save(self.injury, 'external_notes', 'Coach external', write_date=loaded)
        self.assertEqual(resp.status_code, 200, resp.text)
        for write_date in (loaded, None):
            resp = self._save(self.injury, 'internal_notes', 'Coach text', write_date=write_date,
                              old_value='Synthetic internal v1')
            self.assertEqual(resp.status_code, 403, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.sudo().internal_notes, 'Synthetic internal v1')

    # -- RF2 -------------------------------------------------------------
    def test_clear_recorded_in_history(self):
        self._follow()
        self._login_tp()
        resp = self._save(self.injury, 'external_notes', 'Synthetic external')
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._save(self.injury, 'external_notes', '')
        self.assertEqual(resp.status_code, 200, resp.text)
        rows = self._rows('external')
        self.assertEqual([r.content or '' for r in rows], ['Synthetic external', ''])
        self.assertEqual(rows[-1].author_id, self.tp)
        # The history sheet shows the clear.
        resp = self.url_open('/my/injury/%s/notes/history/fragment' % self.injury.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Cleared', resp.text)
        # The player's page and the team digest still render (empty note).
        self._switch(True)
        for url in ('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id),
                    '/my/team?team_id=%s' % self.team_a.id):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
        items = self.player.sudo()._dashboard_change_items('tp')
        self.assertIsInstance(items, list)

    def test_clear_on_injury_without_note_logs_nothing(self):
        self._login_tp()
        before = len(self._rows('external'))
        resp = self._save(self.injury, 'external_notes', '   ')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(self._rows('external')), before)


@tagged('post_install', '-at_install')
class TestReviewFixes1014Pages(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _activity_row(tree, activity):
        rows = tree.xpath('//*[@data-sc-activity-row="%s"]' % activity.id)
        return rows[0]

    # -- RF5 -------------------------------------------------------------
    def test_activity_title_record_name_is_a_link(self):
        self.act_player.summary = 'Call Pat One back'
        self.act_team.summary = 'Bring the PC Team A jerseys'
        self._login_tp()
        _text_, tree = self._get('/my/activities')
        for activity, name, url in (
                (self.act_player, 'Pat One', '/my/player?player_id=%s' % self.player.id),
                (self.act_team, 'PC Team A', '/my/team?team_id=%s' % self.team_a.id)):
            row = self._activity_row(tree, activity)
            title = row.xpath('.//*[@data-sc-title-split]')
            self.assertEqual(len(title), 1, activity.summary)
            self.assertEqual(_text(title[0]), activity.summary)
            links = title[0].xpath('.//a[contains(@class, "o_sc_row_title_link")]')
            self.assertEqual([(a.get('href'), _text(a)) for a in links], [(url, name)])
            main = row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')
            self.assertEqual(len(main), 1)
            self.assertEqual(main[0].get('href'), '/my/activity/%s' % activity.id)
            self.assertEqual(main[0].get('aria-label'), activity.summary)
            self.assertFalse(row.xpath('.//a//a'))
        # A title without a record name stays the plain main link.
        row = self._activity_row(tree, self.act_event)
        self.assertFalse(row.xpath('.//*[@data-sc-title-split]'))
        self.assertEqual(_text(row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')[0]),
                         self.act_event.summary)

    def test_activity_title_name_plain_when_refused(self):
        self.act_player.summary = 'Call Pat One back'
        self._login_tp()
        with patch.object(AccessControlMixin, '_check_access_to_patient',
                          side_effect=AccessError('refused')):
            _text_, tree = self._get('/my/activities')
        row = self._activity_row(tree, self.act_player)
        self.assertFalse(row.xpath('.//*[@data-sc-title-split]'))
        self.assertNotIn('/my/player?player_id=', lxml_html.tostring(row).decode())

    # -- RF6 -------------------------------------------------------------
    def _filter_form(self, tree, section):
        forms = tree.xpath('//form[@data-sc-section="%s"]' % section)
        self.assertEqual(len(forms), 1, section)
        form = forms[0]
        self.assertEqual(form.get('data-sc-autosubmit'), '1', section)
        fallback = form.xpath('.//button[@type="submit"][@data-sc-autosubmit-fallback]')
        self.assertEqual(len(fallback), 1, section)
        return form

    def test_filters_apply_on_change_sort_apart(self):
        self._login_tp()
        # Task 1607 (deliberate update): the sort left the filter panel for
        # the list header; the group by keeps its own labelled group.
        for url, section, group_section in (
                ('/my/events', 'events.filters', 'events.group'),
                ('/my/sc/timesheets', 'timesheets.filters', 'timesheets.group')):
            _text_, tree = self._get(url)
            form = self._filter_form(tree, section)
            group = form.xpath('.//fieldset[@data-sc-section="%s"]' % group_section)
            self.assertEqual(len(group), 1, url)
            self.assertEqual(_text(group[0].xpath('./legend')[0]), 'Group by')
            self.assertEqual(group[0].xpath('.//select/@name'), ['group_by'])
            # The group select is not among the filters; no sort select.
            others = [n for n in form.xpath('.//select/@name') if n != 'group_by']
            self.assertTrue(others, url)
            self.assertFalse(form.xpath('.//select[@name="sortby"]'), url)
        # The calendar shares the bar, without sort / group by.
        _text_, tree = self._get('/my/events/calendar')
        form = self._filter_form(tree, 'events.filters')
        self.assertFalse(form.xpath('.//fieldset[@data-sc-section="events.group"]'))
        _text_, tree = self._get('/my/clinics')
        self._filter_form(tree, 'clinics.filters')

    # -- RF8 -------------------------------------------------------------
    def test_event_form_end_error_next_to_the_field(self):
        self._login_tp()
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(), 'name': 'Synthetic bad times', 'event_type': 'game',
            'team_ids': str(self.team_a.id),
            'date_start': '2026-03-03T18:00', 'date_end': '2026-03-03T17:00',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertFalse(self.env['sports.event'].search([('name', '=', 'Synthetic bad times')]))
        _text_, tree = self._get('/my/event/create')
        error = tree.xpath('//*[@data-sc-field-error="date_end"]')
        self.assertEqual(len(error), 1)
        self.assertEqual(_text(error[0]), 'Event end time must be after start time.')
        self.assertEqual(tree.xpath('//input[@name="date_end"]/@aria-invalid'), ['true'])
        self.assertNotIn('Event end time must be after start time.',
                         ' '.join(_text(b) for b in tree.xpath('//*[contains(@class, "o_sc_banner")]')))
        # On the event page (edited in place), the autosave answers the
        # refusal as the field's own message (400 + message).
        self.event.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.event/%s' % self.event.id, data={
            'field': 'date_end', 'value': '2026-02-02T08:00',
            'write_date': fields.Datetime.to_string(self.event.write_date),
            'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(resp.json()['message'], 'Event end time must be after start time.')

    # -- RF9 -------------------------------------------------------------
    def _add_card(self, tree):
        return tree.xpath('//section[@data-sc-tab-panel="players"]'
                          '/details[@data-sc-section="team.add_player"]')[0]

    def test_add_player_one_set_of_fields(self):
        self._login_tp()
        url = '/my/team?team_id=%s&tab=players' % self.team_a.id
        _text_, tree = self._get(url + '&add_first=Sam&add_last=Newplayer&add_dob=2011-03-04')
        card = self._add_card(tree)
        visible = card.xpath('.//input[not(@type="hidden")]/@name')
        self.assertEqual(sorted(visible), ['add_dob', 'add_first', 'add_last'])
        create = card.xpath('.//form[@data-sc-form="player.create"]')[0]
        hidden = {i.get('name'): (i.get('value'), i.get('data-sc-copy-from'))
                  for i in create.xpath('.//input[@type="hidden"][@data-sc-copy-from]')}
        self.assertEqual(hidden, {
            'first_name': ('Sam', 'add_first'),
            'last_name': ('Newplayer', 'add_last'),
            'date_of_birth': ('2011-03-04', 'add_dob'),
        })
        button = create.xpath('.//button[@data-sc-action="player.create"]')[0]
        self.assertIsNone(button.get('disabled'))
        self.assertEqual(create.xpath('.//*[@data-sc-create-hint]/@hidden'), ['hidden'])
        # The labels « First name » / « Last name » appear once each.
        labels = [_text(lbl) for lbl in card.xpath('.//label')]
        self.assertEqual(labels.count('First name'), 1)
        self.assertEqual(labels.count('Last name'), 1)
        # Only a last name searched: the button waits for a first name.
        _text_, tree = self._get(url + '&add_last=Newplayer')
        create = self._add_card(tree).xpath('.//form[@data-sc-form="player.create"]')[0]
        self.assertEqual(create.xpath('.//button[@data-sc-action="player.create"]/@disabled'), ['disabled'])
        self.assertFalse(create.xpath('.//*[@data-sc-create-hint]/@hidden'))


@tagged('post_install', '-at_install')
class TestReviewFixes1014I18n(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_time_order_messages_in_french(self):
        env = self.env(context=dict(self.env.context, lang='fr_CA'))
        start = fields.Datetime.to_datetime('2026-03-03 18:00:00')
        expected = (
            (env['sports.event'], {
                'name': 'Synthetic bad times', 'event_type': 'game',
                'team_ids': [Command.set(self.team_a.ids)],
                'date_start': start, 'date_end': start.replace(hour=17)},
             "La fin de l'événement doit être après le début."),
            (env['sports.event'], {
                'name': 'Synthetic bad therapist times', 'event_type': 'game',
                'team_ids': [Command.set(self.team_a.ids)],
                'date_start': start, 'date_end': start.replace(hour=20),
                'therapist_start': start, 'therapist_end': start.replace(hour=17)},
             "La fin de la présence du thérapeute doit être après son début."),
        )
        for model, vals, message in expected:
            with self.assertRaises(ValidationError) as caught, mute_logger('odoo.sql_db'):
                with self.env.cr.savepoint():
                    model.create(vals)
            self.assertEqual(str(caught.exception.args[0]), message)
        Timesheet = env['sports.event.timesheet']
        with self.assertRaises(ValidationError) as caught, mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                Timesheet.create({
                    'event_id': self.event.id, 'user_id': self.tp.id,
                    'coverage_start': start, 'coverage_end': start.replace(hour=17)})
        self.assertEqual(str(caught.exception.args[0]),
                         "La fin de la couverture doit être après son début.")

    def test_pages_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/events')
        # Task 1607 (deliberate update): the sort is in the list header.
        self.assertIn('Grouper par', text)
        self.assertIn('Trier les événements', text)
        tree = lxml_html.fromstring(self._fr(
            '/my/team?team_id=%s&tab=players&add_last=Newplayer' % self.team_a.id))
        hint = tree.xpath('//*[@data-sc-create-hint]')[0]
        self.assertEqual(_text(hint), 'Entrez un prénom et un nom ci-dessus pour créer un nouveau joueur.')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(), 'name': 'Synthetic bad times', 'event_type': 'game',
            'team_ids': str(self.team_a.id),
            'date_start': '2026-03-03T18:00', 'date_end': '2026-03-03T17:00',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        tree = lxml_html.fromstring(self._fr('/my/event/create'))
        error = tree.xpath('//*[@data-sc-field-error="date_end"]')
        self.assertEqual([_text(e) for e in error], ["La fin de l'événement doit être après le début."])
        self.event.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.event/%s' % self.event.id, data={
            'field': 'date_end', 'value': '2026-02-02T08:00',
            'write_date': fields.Datetime.to_string(self.event.write_date),
            'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(resp.json()['message'], "La fin de l'événement doit être après le début.")


@tagged('post_install', '-at_install')
class TestReviewFixes1014Tours(PlayerInlineCommon):

    def test_date_saved_once_complete(self):
        self.player.write({'return_date': False})
        self.start_tour(self._url(), 'sc_1014_date_complete', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.return_date, date(2026, 11, 15))

    def test_saves_are_serialized(self):
        self.player.write({'training_recommendation': False})
        self.start_tour(self._url(tab='injuries'), 'sc_1014_serialized_saves', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.training_recommendation, 'Synthetic second')
        rows = self.env['sports.patient.training.history'].search([('patient_id', '=', self.player.id)])
        self.assertEqual(sorted(rows.mapped('content')), ['Synthetic first', 'Synthetic second'])

    def test_filters_apply_on_change(self):
        self.start_tour('/my/events', 'sc_1014_filters_autosubmit', login='pc.tp@example.com')
