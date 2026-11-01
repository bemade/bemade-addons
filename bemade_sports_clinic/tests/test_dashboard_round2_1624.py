"""Task 1624 — owner UAT round 2 (2026-10-29) on the app dashboard.
Synthetic fixtures only (dashboard_common_1624; this repository is public).
The browser half (gap, scroll anchoring, live follow, the quick edit in a
real browser) is test_dashboard_tours_1624 (« sc_1624_dashboard_round2 »).

Acceptance criteria:

* UC-G1 Gap: every widget's body is ONE stack box (``o_sc_dw_body``, the
  card-list gap), so in « Aujourd'hui » the « Cliniques aujourd'hui » row
  and the first event card are two items of that stack, never touching;
  the other widgets' first cards sit in the same box.
* UC-A1 Header stays on screen: the dashboard fold-outs (« À faire » lines,
  « Voir les N autres », the player / event « Détails ») are plain
  summaries / [data-sc-row-expand] toggles with NO autofocus inside; the
  layout script that anchors them is in the bundle. (Measured in the tour:
  8+ cards at 390 and 1440 px, the header moves < 2 px.)
* UC-Q1 Quick « Retour prévu »: each « Retours dépassés » card carries the
  player header's autosave date field (same save route and field, min =
  today, clearable); a past date is refused (#1727 message), a future one
  saves; the next render drops the player from the line (count and list),
  and the card's date carries the hook the page updates in place. A coach
  gets neither the line nor the field.
* UC-E1 Event cards = player cards: Aujourd'hui, Couvertures / Événements
  à venir and Feuilles de temps manquantes render each event as a row
  group (``o_sc_row_group``) with a link row (``sc_link_row``) whose main
  link (« › » chevron) opens the event, and the shared « Détails »
  expander ([data-sc-row-expand], aria-expanded) controlling a details
  region under the row; ids are unique on the page.
* UC-F1 Live follow: each « Joueurs que je suis » instance is a LIST read
  fragment (``sc.dashboard:followed:<instance>``, items = the player cards)
  with its count and its empty state; after a follow / unfollow the
  fragment answer adds / drops the card in every instance, each with its
  own scope.
* UC-C1 Coverage of other teams (owner 2026-10-29): with no « Portée »
  (« Toutes mes équipes »), a therapist's « Couvertures à venir »,
  « Aujourd'hui » and « Feuilles de temps manquantes » list EVERY event
  assigned to them, on any team — one they do not staff included; with a
  scope, only the assigned events of the scoped teams. A coach keeps their
  teams' events (« Événements à venir »).
* UC-Z1 Three zones (owner 2026-10-29): every instance has a ``zone``
  (left / right / bottom); the layout is ``v: 2``. The default is the
  owner's layout, every section on — left: today, todo, coverage,
  missing_timesheets; right: indicators, announcements, followed; bottom:
  recent_changes, watch — with À faire's four kinds, the default coverage
  window, 30 days back, red + yellow; a coach gets the widgets of their
  role in the same relative order.
* UC-Z2 A ``v: 1`` layout still loads: its order kept, the first half
  (rounded up) left, the rest right; widgets it lacks join their default
  zone; the next save writes ``v: 2``. An unknown version = the default.
* UC-Z3 The page renders the zones in phone order (left, right, bottom) —
  one column on a phone; on a laptop (CSS grid) left and right side by
  side, bottom under both; a lone side column spans the width.
* UC-Z4 Placing: ▲ / ▼ stay within the zone; « Déplacer vers » / a drop
  post a zone (and a position) to /configure/move (JSON for fetch); an
  unknown zone is refused (400); « Ajouter une section » takes a zone,
  default the shorter column. « Configurer » shows the three zones, each
  row with its « Move to » control and drag handle.
* UC-Z5 « Rétablir par défaut » gives the default zones back.
"""
import json
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import file_open

from odoo.addons.bemade_sports_clinic.models import sc_dashboard
from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin

XHR = {'X-Requested-With': 'XMLHttpRequest'}


@tagged('post_install', '-at_install')
class TestDashboardRound2_1624(FragmentsMixin, Dashboard1624Common):

    def _overdue(self, player, days=3):
        player.sudo().with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': fields.Date.today() - timedelta(days=days)})

    # -- UC-G1 ---------------------------------------------------------------
    def test_widget_body_stack(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        for section in self._sections(tree):
            if section.get('data-sc-widget') == 'indicators':
                continue
            bodies = section.xpath('./div[contains(@class, "o_sc_dw_body")]')
            self.assertEqual(len(bodies), 1, section.get('data-sc-instance'))
        today = self._section(tree, 'today').xpath('./div[contains(@class, "o_sc_dw_body")]')[0]
        # The clinics row and the event cards are siblings in the stack.
        kids = [child.get('class') or '' for child in today]
        self.assertIn('o_sc_dw_clinics', kids[0])
        self.assertTrue(any('o_sc_dw_events' in k for k in kids[1:]), kids)
        scss = file_open('bemade_sports_clinic/static/src/scss/sc_dashboard.scss').read()
        self.assertIn('.o_sc_dw_body {', scss)

    # -- UC-A1 ---------------------------------------------------------------
    def test_fold_outs_no_autofocus(self):
        self._overdue(self.shared)
        self._login_tp()
        _text, tree = self._get('/my/home')
        dash = tree.xpath('//*[@data-sc-dashboard]')[0]
        self.assertFalse(dash.xpath('.//*[@autofocus]'))
        self.assertTrue(dash.xpath('.//details[@data-sc-todo]/summary'))
        self.assertTrue(dash.xpath('.//button[@data-sc-row-expand]'))
        manifest = file_open('bemade_sports_clinic/__manifest__.py').read()
        self.assertIn('static/src/js/sc_dashboard_live.js', manifest)

    # -- UC-Q1 ---------------------------------------------------------------
    def test_quick_return_edit(self):
        self._overdue(self.shared)
        self._login_tp()
        _text, tree = self._get('/my/home')
        line = self._section(tree, 'todo').xpath('.//details[@data-sc-todo="returns"]')[0]
        card = line.xpath('.//*[@data-sc-player-id="%s"]' % self.shared.id)[0]
        props = json.loads(card.xpath('.//*[@data-sc-row-quick="predicted_return_date"]'
                                      '/owl-component/@props')[0])
        today = fields.Date.to_string(fields.Date.context_today(self.tp))
        self.assertEqual((props['model'], props['recordId'], props['field'], props['inputType']),
                         ('sports.patient', self.shared.id, 'predicted_return_date', 'date'))
        self.assertEqual(props['min'], today)
        self.assertTrue(props['clearable'])
        # The face's date: the hook the page updates in place, « Dépassé » on.
        value = card.xpath('.//*[@data-sc-row-return-value="%s"]' % self.shared.id)[0]
        self.assertIn('o_sc_overdue', value.get('class'))
        self.assertTrue(value.xpath('.//*[@data-sc-row-return-date]'))
        # Unique input ids (one per card and line).
        ids = tree.xpath('//@id')
        self.assertEqual(len(ids), len(set(ids)), [i for i in ids if ids.count(i) > 1])
        # The count is a read fragment of the page.
        key = 'sc.dashboard:todo:dash-todo-returns'
        self.assertEqual(line.xpath('.//*[@data-sc-todo-count]/@data-sc-fragment'), [key])

        # A past date: refused inline (#1727), nothing stored.
        past = fields.Date.today() - timedelta(days=1)
        resp = self._save(self.shared, 'predicted_return_date', fields.Date.to_string(past))
        self.assertNotEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['message'])
        self.assertNotEqual(self.shared.predicted_return_date, past)
        # A future one: saved; the line drops the player on the next render.
        future = fields.Date.today() + timedelta(days=10)
        answer = self._saved(self.shared, 'predicted_return_date', fields.Date.to_string(future))
        self.assertTrue(answer['display'])
        self.assertEqual(self.shared.predicted_return_date, future)
        _text, tree = self._get('/my/home')
        self.assertFalse(self._section(tree, 'todo').xpath('.//details[@data-sc-todo="returns"]'))
        # ... and the count fragment is gone (the page hides the chip).
        self.assertIn(key, self._fragments('/my/home', [key])['missing'])

    def test_quick_return_edit_counts(self):
        self._overdue(self.shared)
        self._overdue(self.red, 5)
        self._login_tp()
        key = 'sc.dashboard:todo:dash-todo-returns'
        node = self._fragment('/my/home', key)
        self.assertEqual(node.text_content().strip(), '2')
        self._saved(self.red, 'predicted_return_date',
                    fields.Date.to_string(fields.Date.today() + timedelta(days=3)))
        node = self._fragment('/my/home', key)
        self.assertEqual(node.text_content().strip(), '1')

    def test_quick_return_edit_not_for_coach(self):
        self._overdue(self.shared)
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//*[@data-sc-row-quick]'))

    # -- UC-E1 ---------------------------------------------------------------
    def test_event_cards_like_player_cards(self):
        start = fields.Datetime.now() - timedelta(days=3)
        self.env['sports.event'].create({
            'name': 'DB Missing R2', 'event_type': 'game',
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'team_ids': [Command.set(self.team_a.ids)],
            'assigned_staff_ids': [Command.set(self.tp.ids)], 'state': 'confirmed'})
        self._login_tp()
        _text, tree = self._get('/my/home')
        for instance_id in ('today', 'coverage', 'missing_timesheets'):
            section = self._section(tree, instance_id)
            groups = section.xpath('.//div[contains(@class, "o_sc_row_group")][@data-sc-event-row]')
            self.assertTrue(groups, instance_id)
            for group in groups:
                event_id = group.get('data-sc-event-row')
                row = group.xpath('./div[contains(@class, "o_sc_link_row")]')
                self.assertEqual(len(row), 1, instance_id)
                main = row[0].xpath('.//a[contains(@class, "o_sc_link_row_main")]')[0]
                self.assertIn('/my/event/%s' % event_id, main.get('href'))
                self.assertEqual(main.get('data-sc-event-id'), event_id)
                # The « › » chevron on the right.
                self.assertTrue(row[0].xpath('./span[@class="o_sc_row_trailing"]//*[local-name()="svg"]'))
                # The shared expander, controlling the region under the row.
                toggle = row[0].xpath('.//button[@data-sc-row-expand]')[0]
                self.assertEqual(toggle.get('aria-expanded'), 'false')
                region = group.xpath('./div[@id="%s"]' % toggle.get('data-sc-row-expand'))[0]
                self.assertEqual(region.get('data-sc-event-details'), event_id)
                self.assertEqual(region.get('hidden'), 'hidden')
                self.assertIn('o_sc_row_detail', region.get('class'))
        # « Add my timesheet » stays on the missing ones.
        self.assertTrue(self._section(tree, 'missing_timesheets').xpath(
            './/a[@data-sc-action="dashboard.timesheet.add"]'))
        ids = tree.xpath('//@id')
        self.assertEqual(len(ids), len(set(ids)), [i for i in ids if ids.count(i) > 1])

    # -- UC-F1 ---------------------------------------------------------------
    def test_followed_is_a_list_fragment(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'followed')
        self.assertEqual(section.get('data-sc-fragment'), 'sc.dashboard:followed:followed')
        self.assertEqual(section.get('data-sc-fragment-mode'), 'list')
        self.assertEqual(section.get('data-sc-fragment-keep-empty'), '1')
        self.assertTrue(section.xpath('.//*[contains(@class, "o_sc_empty")]'))
        self.assertFalse(section.xpath('.//*[@data-sc-dw-count]'))

    def test_follow_refreshes_every_instance(self):
        # A second instance scoped to Team C (Yellow, Shared; not Red).
        new_id = self._dash(self.tp)._sc_layout_add('followed')
        self._dash(self.tp)._sc_layout_update(new_id, settings={'scope_team_ids': [self.team_c.id]})
        keys = ['sc.dashboard:followed:followed', 'sc.dashboard:followed:%s' % new_id]
        self._login_tp()
        csrf = self._csrf()

        def follow(player, on):
            resp = self.url_open('/my/player/%s/follow' % player.id, headers=XHR, data={
                'follow': '1' if on else '0', 'csrf_token': csrf}, allow_redirects=False)
            self.assertEqual(resp.json(), {'ok': True, 'followed': on})

        def cards(payload, key):
            node = lxml_html.fragment_fromstring(payload['fragments'][key])
            items = node.xpath('.//*[@data-sc-fragment-item]/@data-sc-fragment-item')
            self.assertEqual(len(items), len(set(items)))
            return items, node

        follow(self.red, True)
        payload = self._fragments('/my/home', keys)
        items, node = cards(payload, keys[0])
        self.assertEqual(items, ['p%s' % self.red.id])
        self.assertEqual(node.xpath('.//*[@data-sc-dw-count]')[0].text_content().strip(), '(1)')
        # The scoped instance: Red is not on Team C — still empty.
        items, node = cards(payload, keys[1])
        self.assertEqual(items, [])
        self.assertTrue(node.xpath('.//*[contains(@class, "o_sc_empty")]'))

        follow(self.yellow, True)
        payload = self._fragments('/my/home', keys)
        self.assertEqual(sorted(cards(payload, keys[0])[0]),
                         sorted(['p%s' % self.red.id, 'p%s' % self.yellow.id]))
        self.assertEqual(cards(payload, keys[1])[0], ['p%s' % self.yellow.id])

        follow(self.red, False)
        follow(self.yellow, False)
        payload = self._fragments('/my/home', keys)
        for key in keys:
            items, node = cards(payload, key)
            self.assertEqual(items, [], key)
            self.assertTrue(node.xpath('.//*[contains(@class, "o_sc_empty")]'), key)

    # -- UC-C1 ---------------------------------------------------------------
    def test_assigned_events_on_any_team(self):
        """Team B: nobody of ours staffs it; the therapist covers its events."""
        now = fields.Datetime.now()
        Event = self.env['sports.event']

        def _event(name, start):
            return Event.create({
                'name': name, 'event_type': 'game', 'date_start': start,
                'date_end': start + timedelta(hours=2), 'state': 'confirmed',
                'team_ids': [Command.set(self.team_b.ids)],
                'assigned_staff_ids': [Command.set(self.tp.ids)]})

        upcoming = _event('DB Cover B', now + timedelta(days=2))
        today = _event('DB Cover B Today', now.replace(hour=12, minute=0, second=0, microsecond=0))
        past = _event('DB Cover B Past', now - timedelta(days=2))
        # The assignment gives a temporary coverage staff row (task 539);
        # drop it: the team is one I do not staff at all.
        self.env['sports.team.staff'].sudo().search([
            ('team_id', '=', self.team_b.id), ('partner_id', '=', self.tp.partner_id.id)]).unlink()
        self.assertNotIn(self.team_b, self._dash(self.tp)._sc_staffed_teams())

        def ids(tree, instance_id):
            return {int(i) for i in self._section(tree, instance_id).xpath(
                './/*[@data-sc-event-id]/@data-sc-event-id')}

        self._login_tp()
        _text, tree = self._get('/my/home')
        self.assertIn(upcoming.id, ids(tree, 'coverage'))
        self.assertIn(today.id, ids(tree, 'today'))
        self.assertIn(past.id, ids(tree, 'missing_timesheets'))
        # Scope = my own Team A only: the Team B coverage is not listed.
        for instance_id in ('coverage', 'missing_timesheets'):
            self._dash(self.tp)._sc_layout_update(
                instance_id, settings={'scope_team_ids': self.team_a.ids})
        _text, tree = self._get('/my/home')
        self.assertNotIn(upcoming.id, ids(tree, 'coverage'))
        self.assertIn(self.ev_soon.id, ids(tree, 'coverage'))
        self.assertNotIn(past.id, ids(tree, 'missing_timesheets'))
        # « Aujourd'hui » is personal (not scoped): still there.
        self.assertIn(today.id, ids(tree, 'today'))
        # A coach: their teams' events, never Team B's.
        coach_events = self._dash(self.coach)._sc_data_coverage(
            self.env['sports.team'].browse((self.team_a | self.team_c).ids), 7, False)
        self.assertNotIn(upcoming, coach_events)
        self.assertIn(self.ev_soon, coach_events)

    # -- UC-Z1 ---------------------------------------------------------------
    DEFAULT_ZONES = {
        'left': ['today', 'todo', 'coverage', 'missing_timesheets'],
        'right': ['indicators', 'announcements', 'followed'],
        'bottom': ['recent_changes', 'watch'],
    }

    def _zones(self, layout):
        return {zone: [inst['id'] for inst in layout if inst['zone'] == zone]
                for zone in sc_dashboard.ZONES}

    def test_default_zones(self):
        layout = self._dash(self.tp)._sc_layout()
        self.assertEqual(self._zones(layout), self.DEFAULT_ZONES)
        self.assertTrue(all(inst['enabled'] for inst in layout))
        by_id = {inst['id']: inst for inst in layout}
        self.assertEqual(by_id['todo']['settings']['kinds'], list(sc_dashboard.TODO_KINDS))
        self.assertEqual(by_id['coverage']['settings']['days'], 0)
        self.assertEqual(by_id['missing_timesheets']['settings']['days_back'], 30)
        self.assertEqual(by_id['watch']['settings']['level'], 'red_yellow')
        self.assertFalse(any(inst['settings'].get('scope_team_ids') for inst in layout))
        # A coach: their widgets, same relative order and zones.
        coach = self._zones(self._dash(self.coach)._sc_layout())
        self.assertEqual(coach, dict(self.DEFAULT_ZONES, left=['today', 'todo', 'coverage']))

    # -- UC-Z2 ---------------------------------------------------------------
    def test_v1_layout_migrates(self):
        old = ['today', 'todo', 'coverage', 'missing_timesheets', 'indicators', 'announcements',
               'followed', 'recent_changes', 'watch']
        self.tp.sudo().sc_dashboard_layout = {'v': 1, 'instances': [
            {'id': key, 'widget': key, 'enabled': key not in ('recent_changes', 'watch'),
             'settings': {'level': 'red'} if key == 'watch' else {}} for key in old]}
        dash = self._dash(self.tp)
        layout = dash._sc_layout()
        self.assertEqual([inst['id'] for inst in layout], old)
        self.assertEqual(self._zones(layout), {
            'left': old[:5], 'right': old[5:], 'bottom': []})
        self.assertFalse(next(i for i in layout if i['id'] == 'watch')['enabled'])
        self.assertEqual(next(i for i in layout if i['id'] == 'watch')['settings']['level'], 'red')
        # A v1 with fewer sections: the missing ones join their default zone.
        self.tp.sudo().sc_dashboard_layout = {'v': 1, 'instances': [
            {'id': key, 'widget': key, 'enabled': True, 'settings': {}}
            for key in ('watch', 'today', 'indicators')]}
        zones = self._zones(dash._sc_layout())
        self.assertEqual(zones['left'][:2], ['watch', 'today'])
        self.assertEqual(zones['right'][0], 'indicators')
        self.assertEqual(zones['bottom'], ['recent_changes'])
        # The next save writes v2, zones included.
        dash._sc_layout_update('today', title='Mine')
        stored = self.tp.sudo().sc_dashboard_layout
        self.assertEqual(stored['v'], 2)
        self.assertTrue(all(inst['zone'] in sc_dashboard.ZONES for inst in stored['instances']))
        # Unknown version: the default.
        self.tp.sudo().sc_dashboard_layout = {'v': 3, 'instances': []}
        self.assertEqual(self._zones(dash._sc_layout()), self.DEFAULT_ZONES)
        # A v2 save without zones / with a bad zone is refused.
        layout = dash._sc_layout()
        with self.assertRaises(ValidationError):
            dash._sc_layout_save([dict(layout[0], zone='middle')] + layout[1:])

    # -- UC-Z3 ---------------------------------------------------------------
    def test_zone_render_order(self):
        self._dash(self.tp)._sc_layout_place('watch', 'left', 0)
        self._login_tp()
        _text, tree = self._get('/my/home')
        dash = tree.xpath('//*[@data-sc-dashboard]')[0]
        zones = dash.xpath('./div[@data-sc-zone]')
        self.assertEqual([z.get('data-sc-zone') for z in zones], ['left', 'right', 'bottom'])
        got = {z.get('data-sc-zone'): [s.get('data-sc-instance') for s in z.xpath('./section')]
               for z in zones}
        self.assertEqual(got['left'], ['watch'] + self.DEFAULT_ZONES['left'])
        self.assertEqual(got['bottom'], ['recent_changes'])
        # Phone order = document order: left, right, bottom.
        self.assertEqual([s.get('data-sc-instance') for s in self._sections(tree)],
                         got['left'] + got['right'] + got['bottom'])
        scss = file_open('bemade_sports_clinic/static/src/scss/sc_dashboard.scss').read()
        self.assertIn('grid-template-areas: "left right" "bottom bottom"', scss)
        self.assertNotIn('column-count', scss)
        # Only one side column used: it spans the width.
        for key in ('indicators', 'announcements', 'followed'):
            self._dash(self.tp)._sc_layout_place(key, 'bottom')
        _text, tree = self._get('/my/home')
        zones = tree.xpath('//*[@data-sc-dashboard]/div[@data-sc-zone]')
        self.assertEqual([z.get('data-sc-zone') for z in zones], ['left', 'bottom'])
        self.assertIn('o_sc_dash_zone_solo', zones[0].get('class'))

    # -- UC-Z4 ---------------------------------------------------------------
    def test_place_routes_and_add_zone(self):
        dash = self._dash(self.tp)
        # ▲ / ▼ within the zone only.
        dash._sc_layout_move('indicators', -1)
        self.assertEqual(self._zones(dash._sc_layout())['right'][0], 'indicators')
        self._login_tp()
        csrf = self._csrf()

        def move(**data):
            return self.url_open('/my/app/dashboard/configure/move', headers=XHR, allow_redirects=False,
                                 data=dict(data, csrf_token=csrf))

        resp = move(instance_id='today', zone='right', position='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json(), {'ok': True})
        zones = self._zones(dash._sc_layout())
        self.assertEqual(zones['right'][:2], ['indicators', 'today'])
        self.assertNotIn('today', zones['left'])
        resp = move(instance_id='today', zone='bottom')  # « Move to »: the end
        self.assertEqual(self._zones(dash._sc_layout())['bottom'][-1], 'today')
        resp = move(instance_id='today', zone='middle')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._zones(dash._sc_layout())['bottom'][-1], 'today')
        # Add: default = the shorter column (left 3 vs right 3 -> left on a
        # tie; then right 3 < left 4 -> right); an explicit zone wins.
        self.assertEqual(dash._sc_layout_add('watch'), 'watch-2')
        self.assertEqual(self._instance(self.tp, 'watch-2')['zone'], 'left')
        dash._sc_layout_add('watch')
        self.assertEqual(self._instance(self.tp, 'watch-3')['zone'], 'right')
        dash._sc_layout_add('watch', zone='bottom')
        self.assertEqual(self._instance(self.tp, 'watch-4')['zone'], 'bottom')
        # « Configurer »: three zones, each row with its controls.
        _text, tree = self._get('/my/app/dashboard/configure')
        lists = tree.xpath('//ol[@data-sc-dash-zone]')
        self.assertEqual([ol.get('data-sc-dash-zone') for ol in lists], ['left', 'right', 'bottom'])
        for ol in lists:
            for item in ol.xpath('./li[@data-sc-dash-item]'):
                self.assertTrue(item.xpath('.//*[@data-sc-dash-drag]'))
                select = item.xpath('.//select[@data-sc-dash-zone-select]')[0]
                self.assertEqual(select.xpath('./option[@selected]/@value'), [ol.get('data-sc-dash-zone')])
            items = ol.xpath('./li[@data-sc-dash-item]')
            if items:
                self.assertTrue(items[0].xpath('.//button[@data-sc-dash-move="up"][@disabled]'))
                self.assertTrue(items[-1].xpath('.//button[@data-sc-dash-move="down"][@disabled]'))
        add_zone = tree.xpath('//select[@id="sc_dash_add_zone"]/option[@selected]/@value')
        self.assertEqual(len(add_zone), 1)

    # -- UC-Z5 ---------------------------------------------------------------
    def test_reset_gives_default_zones(self):
        dash = self._dash(self.tp)
        dash._sc_layout_place('today', 'bottom')
        dash._sc_layout_update('watch', enabled=False)
        dash._sc_layout_reset()
        layout = dash._sc_layout()
        self.assertEqual(self._zones(layout), self.DEFAULT_ZONES)
        self.assertTrue(all(inst['enabled'] for inst in layout))
