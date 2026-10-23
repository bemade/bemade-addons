"""Task 1607 — « + Ajouter » just above each list, the sort condensed to the
right, no list action left in the app bar. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-H1 The app bar carries no page action on any shell page (no
  ``o_sc_appbar_action`` / action slot): only the app-wide items.
* UC-H2 One list header (``.o_sc_list_header``) right above each list: its
  « + Ajouter » always reads « Add » (« Ajouter »), its accessible name is the
  full action (``aria-label``), and it reaches the SAME target as before —
  a link (players « Create a player », events « New event » on the list's
  organization filter + above the calendar, activities « Add Activity »), a
  sheet (clinic « Add a patient », the event's « Add My Timesheet », an
  injury card's « Add documents ») or the inline panel right under the
  header (``aria-controls`` = the ``<details>`` id; team « Add a player » /
  « Request a player addition », the player page's injuries, notes,
  activities, emergency contacts, documents, the clinic dossier's injuries
  and notes, the team's activities, the notepad's quick note).
* UC-H3 The sort is a compact menu on the right of the header — the same
  control everywhere (``[role=menuitemradio]`` links, the active one
  ``aria-checked``): players (by status / alphabetical), team roster (by
  status / by number), teams (recent activity / alphabetical / my order),
  events and timesheets (moved out of the filter panel; the filter form
  keeps the chosen sort as a hidden field). Each option keeps the page's
  other query parameters and drops the pager / flash ones.
* UC-H4 The event page's « + Ajouter » is a read fragment: assigning
  yourself to the event offers it in place (the section shows up), removing
  yourself takes it away.
* UC-H5 fr_CA: « Ajouter », the sort labels and the full actions.
"""
from urllib.parse import parse_qs, urlsplit

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common


def _q(href):
    parts = urlsplit(href)
    return parts.path, {key: values[0] for key, values in parse_qs(parts.query).items()}


class ListHeader1607Common(Clinic1540Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _headers(tree, section=None):
        xpath = '//div[contains(concat(" ", @class, " "), " o_sc_list_header ")]'
        if section:
            xpath += '[@data-sc-section="%s"]' % section
        return tree.xpath(xpath)

    def _header(self, tree, section):
        headers = self._headers(tree, section)
        self.assertEqual(len(headers), 1, section)
        return headers[0]

    def _add(self, header):
        adds = header.xpath('.//*[contains(concat(" ", @class, " "), " o_sc_list_add ")]')
        self.assertEqual(len(adds), 1)
        add = adds[0]
        self.assertEqual(' '.join(add.text_content().split()), 'Add')
        return add

    @staticmethod
    def _sorts(header):
        return {a.get('data-sc-sort'): a for a in header.xpath('.//a[@role="menuitemradio"]')}

    @staticmethod
    def _checked(header):
        return header.xpath('.//a[@role="menuitemradio"][@aria-checked="true"]/@data-sc-sort')

    def assertNoAppBarAction(self, tree):
        bar = tree.xpath('//header[contains(@class, "o_sc_appbar")]')[0]
        self.assertFalse(bar.xpath('.//*[contains(@class, "o_sc_appbar_action")]'))
        self.assertFalse(bar.xpath('.//*[@data-sc-action]'))
        self.assertFalse(bar.xpath('.//*[@data-sc-sheet-open]'))

    def assertPanelFollows(self, header, panel_id):
        add = self._add(header)
        self.assertEqual(add.tag, 'button')
        self.assertEqual(add.get('aria-controls'), panel_id)
        self.assertEqual(add.get('data-sc-list-add-toggle'), '1')
        panel = header.getnext()
        self.assertIsNotNone(panel)
        self.assertEqual(panel.tag, 'details')
        self.assertEqual(panel.get('id'), panel_id)
        self.assertIn('o_sc_list_add_panel', panel.get('class'))
        return add, panel


@tagged('post_install', '-at_install')
class TestListHeader1607(ListHeader1607Common):

    # -- UC-H1 -----------------------------------------------------------
    def test_app_bar_has_no_page_action(self):
        self._login_tp()
        for url in ('/my/players', '/my/events', '/my/events/calendar', '/my/activities',
                    '/my/clinic/%s' % self.clinic.id, '/my/event/%s' % self.event.id,
                    '/my/team?team_id=%s' % self.team_a.id, '/my/teams', '/my/notepad',
                    '/my/sc/timesheets', '/my/player?player_id=%s' % self.player.id):
            _text, tree = self._get(url)
            self.assertNoAppBarAction(tree)
            self.assertNotIn('o_sc_appbar_action', _text, url)

    # -- UC-H2 / UC-H3: players --------------------------------------------
    def test_players_header_add_and_sort(self):
        self._login_tp()
        _text, tree = self._get('/my/players?first_name=Pat&page=2&success=1')
        header = self._header(tree, 'players.header')
        add = self._add(header)
        self.assertEqual((add.tag, add.get('href')), ('a', '/my/player/create'))
        self.assertEqual(add.get('aria-label'), 'Create a player')
        self.assertEqual(add.get('data-sc-action'), 'players.create')
        self.assertTrue(header.xpath('.//*[contains(@class, "o_sc_list_header_count")]'))
        sorts = self._sorts(header)
        self.assertEqual(sorted(sorts), ['name', 'status'])
        path, query = _q(sorts['name'].get('href'))
        self.assertEqual((path, query), ('/my/players', {'first_name': 'Pat', 'sort': 'name'}))
        self.assertEqual(len(self._checked(header)), 1)
        self.assertEqual(header.xpath('.//*[@data-sc-section="players.sort"]//button/@aria-controls'),
                         ['sc_players_sort'])
        # The header sits right above the list.
        self.assertEqual(header.getnext().get('data-sc-section'), 'players.list')

    def test_players_header_coach_has_no_add(self):
        self._login_coach()
        _text, tree = self._get('/my/players')
        header = self._header(tree, 'players.header')
        self.assertFalse(header.xpath('.//*[contains(@class, "o_sc_list_add")]'))
        self.assertTrue(self._sorts(header))

    # -- events ------------------------------------------------------------
    def test_events_header_add_and_sort_out_of_the_filters(self):
        self._login_tp()
        _text, tree = self._get('/my/events?no_default_dates=1&organization_id=%s&sortby=name' % self.org.id)
        header = self._header(tree, 'events.header')
        add = self._add(header)
        self.assertEqual(add.get('href'), '/my/event/create?organization_id=%s' % self.org.id)
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('New event', 'events.create'))
        self.assertEqual(sorted(self._sorts(header)), ['assigned', 'date', 'date_desc', 'name', 'team'])
        self.assertEqual(self._checked(header), ['name'])
        _path, query = _q(self._sorts(header)['team'].get('href'))
        self.assertEqual(query, {'no_default_dates': '1', 'organization_id': str(self.org.id), 'sortby': 'team'})
        form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
        self.assertFalse(form.xpath('.//select[@name="sortby"]'))
        self.assertEqual(form.xpath('.//input[@type="hidden"][@name="sortby"]/@value'), ['name'])
        self.assertEqual(form.xpath('.//fieldset[@data-sc-section="events.group"]//select/@name'), ['group_by'])
        self.assertIn(header.getnext().get('data-sc-section'), ('events.list', None))
        # The calendar: the add above it, no sort.
        _text, tree = self._get('/my/events/calendar')
        header = self._header(tree, 'events.header')
        self.assertEqual(self._add(header).get('href'), '/my/event/create')
        self.assertFalse(self._sorts(header))
        self.assertEqual(header.getnext().get('data-sc-section'), 'calendar')

    def test_events_coach_no_add(self):
        self._login_coach()
        _text, tree = self._get('/my/events')
        header = self._header(tree, 'events.header')
        self.assertFalse(header.xpath('.//*[contains(@class, "o_sc_list_add")]'))

    # -- activities ----------------------------------------------------------
    def test_activities_header_add(self):
        self._login_tp()
        url = '/my/team/activities?team_id=%s' % self.team_a.id
        _text, tree = self._get(url)
        header = self._header(tree, 'activities.header')
        add = self._add(header)
        self.assertEqual(add.tag, 'a')
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('Add Activity', 'activity.add'))
        path, query = _q(add.get('href'))
        self.assertEqual((path, query['model'], query['res_id']),
                         ('/my/activity/create', 'sports.team', str(self.team_a.id)))
        # Above the lists: the tabs, then the header, then the tab panels.
        following = header.getnext()
        self.assertTrue(following.get('data-sc-tab-panel') or following.get('data-sc-section') == 'activities.list',
                        following.attrib)
        # The plain « my activities » list has nothing to add to.
        _text, tree = self._get('/my/activities')
        self.assertFalse(self._headers(tree, 'activities.header'))

    # -- clinic ------------------------------------------------------------
    def test_clinic_worklist_and_dossier_headers(self):
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient_id=%s' % (self.clinic.id, self.player.id))
        header = self._header(tree, 'clinic.worklist.header')
        add = self._add(header)
        self.assertEqual((add.tag, add.get('data-sc-sheet-open')), ('button', 'sc_clinic_add_sheet'))
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('Add a patient', 'clinic.add'))
        self.assertEqual(header.getnext().tag, 'owl-component')
        self.assertTrue(tree.xpath('//dialog[@id="sc_clinic_add_sheet"]'))
        injuries = tree.xpath('//section[@data-sc-section="clinic.dossier.injuries"]')[0]
        add, _panel = self.assertPanelFollows(self._header(injuries, 'injury.new.header'), 'sc_clinic_injury_add')
        self.assertEqual(add.get('aria-label'), 'Add Injury')
        notes = tree.xpath('//section[@data-sc-section="clinic.dossier.notes"]')[0]
        add, panel = self.assertPanelFollows(self._header(notes, 'notes.add.header'), 'sc_note_add')
        self.assertEqual(add.get('aria-label'), 'Add Treatment Note')
        # Docked open on the clinic, as before.
        self.assertEqual((add.get('aria-expanded'), panel.get('open')), ('true', 'open'))

    # -- event page ----------------------------------------------------------
    def test_event_timesheets_header(self):
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        section = tree.xpath('//section[@data-sc-section="event.timesheets"]')[0]
        header = self._header(section, 'event.timesheets.header')
        add = self._add(header)
        self.assertEqual((add.tag, add.get('data-sc-sheet-open')), ('button', 'sc_ts_add_sheet'))
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('Add My Timesheet', 'timesheet.add'))
        self.assertEqual(header.getparent().get('data-sc-fragment'), 'sports.event:%s:ts-head' % self.event.id)
        # The list follows the header holder.
        self.assertIn('o_sc_list', header.getparent().getnext().get('class'))

    def test_event_coach_has_no_timesheets_section(self):
        self._login_coach()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        self.assertFalse(tree.xpath('//section[@data-sc-section="event.timesheets"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-action="timesheet.add"]'))

    # -- team ----------------------------------------------------------------
    def test_team_roster_header(self):
        self._login_tp()
        _text, tree = self._get('/my/team?team_id=%s&tab=players&add_first=Pat&add_last=One' % self.team_a.id)
        header = self._header(tree, 'team.roster.header')
        add, panel = self.assertPanelFollows(header, 'sc_add_player')
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('Add a player', 'team.add_player'))
        # A search keeps the panel open (as before).
        self.assertEqual((add.get('aria-expanded'), panel.get('open')), ('true', 'open'))
        sorts = self._sorts(header)
        self.assertEqual(sorted(sorts), ['number', 'status'])
        self.assertEqual(self._checked(header), ['status'])
        _path, query = _q(sorts['number'].get('href'))
        self.assertEqual(query, {'team_id': str(self.team_a.id), 'tab': 'players', 'sort': 'number'})
        self.assertEqual(panel.getnext().get('data-sc-section'), 'team.roster')
        _text, tree = self._get('/my/team?team_id=%s&sort=number' % self.team_a.id)
        self.assertEqual(self._checked(self._header(tree, 'team.roster.header')), ['number'])

    def test_team_roster_coach_requests_an_addition(self):
        self._login_coach()
        _text, tree = self._get('/my/team?team_id=%s&tab=players' % self.team_a.id)
        header = self._header(tree, 'team.roster.header')
        add = self._add(header)
        if add.get('aria-controls') == 'sc_request_add':
            self.assertPanelFollows(header, 'sc_request_add')
            self.assertEqual(add.get('aria-label'), 'Request a player addition')
        else:
            self.assertPanelFollows(header, 'sc_add_player')

    def test_team_activities_header(self):
        self._login_tp()
        _text, tree = self._get('/my/team?team_id=%s&tab=activities' % self.team_a.id)
        panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')
        if panel:
            add, _panel = self.assertPanelFollows(self._header(panel[0], 'activity.add.header'), 'sc_activity_add')
            self.assertEqual(add.get('aria-label'), 'Add Activity')

    # -- teams list ------------------------------------------------------------
    def test_teams_sort_in_the_header(self):
        self._login_tp()
        _text, tree = self._get('/my/teams?search=PC&sort=alpha')
        header = self._header(tree, 'teams.header')
        self.assertFalse(header.xpath('.//*[contains(@class, "o_sc_list_add")]'))
        sorts = self._sorts(header)
        self.assertIn('activity', sorts)
        self.assertIn('alpha', sorts)
        self.assertEqual(self._checked(header), ['alpha'])
        _path, query = _q(sorts['activity'].get('href'))
        self.assertEqual(query, {'search': 'PC', 'sort': 'activity'})

    # -- player page -----------------------------------------------------------
    def test_player_page_list_headers(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        expected = (
            ('injuries', 'injury.new.header', 'sc_new_injury', 'Add Injury'),
            ('notes', 'notes.add.header', 'sc_note_add', 'Add Treatment Note'),
            ('activities', 'activity.add.header', 'sc_activity_add', 'Add Activity'),
            ('documents', 'documents.upload.header', 'sc_documents_upload', 'Upload a document'),
        )
        for tab, section, panel_id, label in expected:
            panel = tree.xpath('//section[@data-sc-tab-panel="%s"]' % tab)[0]
            add, _details = self.assertPanelFollows(self._header(panel, section), panel_id)
            self.assertEqual(add.get('aria-label'), label, tab)
            self.assertEqual(add.get('aria-expanded'), 'false', tab)
        contacts = tree.xpath('//section[@data-sc-section="player.info.emergency_contacts"]')[0]
        add, _details = self.assertPanelFollows(self._header(contacts, 'contact.add.header'), 'sc_contact_add')
        self.assertEqual(add.get('aria-label'), 'Add Emergency Contact')

    def test_coach_reports_an_injury(self):
        self._login_coach()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        panel = tree.xpath('//section[@data-sc-tab-panel="injuries"]')[0]
        add, _details = self.assertPanelFollows(self._header(panel, 'injury.new.header'), 'sc_new_injury')
        self.assertEqual(add.get('aria-label'), 'Report Injury')

    def test_injury_card_documents_header(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id))
        docs = tree.xpath('//section[@data-sc-section="injury.documents"]')[0]
        header = self._header(docs, 'injury.documents.header')
        add = self._add(header)
        self.assertEqual(add.get('data-sc-sheet-open'), 'sc_injury_%s_documents_add' % self.injury.id)
        self.assertEqual((add.get('aria-label'), add.get('data-sc-action')), ('Add documents', 'injury.documents.add'))
        self.assertFalse(docs.xpath('.//*[contains(@class, "o_sc_edit_card_head")]//button'))

    # -- notepad / timesheets ---------------------------------------------------
    def test_notepad_header(self):
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        add, panel = self.assertPanelFollows(self._header(tree, 'notepad.header'), 'sc_notepad_add')
        self.assertEqual(add.get('aria-label'), 'Add a note')
        self.assertEqual((add.get('aria-expanded'), panel.get('open')), ('true', 'open'))
        self.assertEqual(panel.xpath('.//form/@action'), ['/my/notepad/add'])

    def test_timesheets_sort_in_the_header(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets?team_id=%s&sortby=state' % self.team_a.id)
        header = self._header(tree, 'timesheets.header')
        self.assertFalse(header.xpath('.//*[contains(@class, "o_sc_list_add")]'))
        sorts = self._sorts(header)
        self.assertEqual(sorted(sorts), ['date', 'date_desc', 'org', 'state', 'team'])
        self.assertEqual(self._checked(header), ['state'])
        _path, query = _q(sorts['date_desc'].get('href'))
        self.assertEqual(query, {'team_id': str(self.team_a.id), 'sortby': 'date_desc'})
        form = tree.xpath('//form[@data-sc-section="timesheets.filters"]')[0]
        self.assertFalse(form.xpath('.//select[@name="sortby"]'))
        self.assertEqual(form.xpath('.//input[@type="hidden"][@name="sortby"]/@value'), ['state'])
        self.assertEqual(form.xpath('.//fieldset[@data-sc-section="timesheets.group"]//select/@name'), ['group_by'])


@tagged('post_install', '-at_install')
class TestListHeaderFragment1607(FragmentsMixin, ListHeader1607Common):

    def _ekey(self, part):
        return 'sports.event:%s:%s' % (self.event.id, part)

    # -- UC-H4 ---------------------------------------------------------------
    def test_assigning_yourself_offers_the_add_in_place(self):
        self._login_tp()
        url = '/my/event/%s' % self.event.id
        self.event.sudo().assigned_staff_ids = [Command.clear()]
        _text, tree = self._get(url)
        section = tree.xpath('//section[@data-sc-section="event.timesheets"]')
        self.assertTrue(section, 'the section holder is there for an editing therapist')
        self.assertFalse(section[0].xpath('.//*[@data-sc-action="timesheet.add"]'))
        self.event.sudo().assigned_staff_ids = [Command.set([self.tp.id])]
        answer = self._fragments(url, [self._ekey('ts-head'), self._ekey('ts-title'), self._ekey('ts-add')])
        self.assertIn('data-sc-action="timesheet.add"', answer['fragments'][self._ekey('ts-head')])
        self.assertIn('My Timesheets', answer['fragments'][self._ekey('ts-title')])
        self.assertIn('sc_ts_add_sheet', answer['fragments'][self._ekey('ts-add')])
        self.assertFragmentMatchesPage(url, self._ekey('ts-head'))


@tagged('post_install', '-at_install')
class TestListHeaderI18n1607(ListHeader1607Common):

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
        cls.tp.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text, tree = self._get(url)
        return text, tree

    # -- UC-H5 ---------------------------------------------------------------
    def test_list_headers_in_french(self):
        self._login_tp()
        _text, tree = self._fr('/my/players')
        header = self._header(tree, 'players.header')
        add = header.xpath('.//*[contains(@class, "o_sc_list_add")]')[0]
        self.assertEqual(' '.join(add.text_content().split()), 'Ajouter')
        self.assertEqual(add.get('aria-label'), 'Créer un joueur')
        labels = [' '.join(a.text_content().split()) for a in header.xpath('.//a[@role="menuitemradio"]')]
        self.assertEqual(labels, ['Par statut', 'Alphabétique'])
        self.assertIn('Trier les joueurs', header.text_content())
        _text, tree = self._fr('/my/sc/timesheets')
        header = self._header(tree, 'timesheets.header')
        self.assertIn('Trier les feuilles de temps', header.text_content())
        text, tree = self._fr('/my/notepad')
        add = self._header(tree, 'notepad.header').xpath('.//button')[0]
        self.assertEqual(add.get('aria-label'), 'Ajouter une note')
        _text, tree = self._fr('/my/events')
        header = self._header(tree, 'events.header')
        self.assertIn('Trier les événements', header.text_content())
        self.assertIn('Grouper par', ' '.join(tree.xpath(
            '//fieldset[@data-sc-section="events.group"]/legend/text()')))
