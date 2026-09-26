"""Task 1421 — player jersey number, shown « #12 » BEFORE the name.

ONE number per player (patient-level, ``sports.patient.jersey_number``), a
Char so « 00 » survives, routed through the task-1414 label helpers so every
portal list / card / heading / picker / digest renders it the same way.

Covered here (synthetic fixtures — this addon's repository is public):

* model helpers: ``_jersey_label`` / ``_portal_list_name`` (« #12 Last, First »
  and, with no number, exactly the 1414 label) / ``_portal_heading_name``
  (« #12 First Last ») / ``_portal_combo_key`` (matches « 12 » and « #12 ») /
  ``_portal_combo_options``; the stored ``jersey_sort`` helper (2 < 10 < 12,
  blanks last); input normalisation (« #12 » → « 12 », blank → False);
* AC1 create + edit round trips through the portal routes, TP and coach,
  incl. the ``_create_portal_patient`` whitelist fix (``position`` was silently
  dropped on portal create; ``jersey_number`` goes through the same gate);
* AC2 the display sites reachable from a server test: player cards
  (/my/players, roster tab), clinic worklist row, picker option label +
  data-key, player page H1, clinic dossier card, player search results, digest
  payload; AC3 no number → labels identical to before (no stray « # »);
* AC4 roster tab « Sort: Number » (2 < 10 < 12, blanks last), sticky per user,
  default order unchanged;
* AC5 duplicate-number warning on a shared team only, never blocking;
* AC6 backend form/list/search declare the field; the merge wizard case lives
  in test_patient_merge_conflicts.

NOT claimed: the look of the six display sites, the sort toggle, the flash
banner and the picker typeahead in a browser — that is the /dev-review
click-through (coach + TP, phone width and laptop).
"""
import re
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestJerseyNumberModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.env.user.sudo().group_ids = [
            Command.link(env.ref(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
        ]
        cls.team_a = env['sports.team'].create({'name': 'JN Team A'})
        cls.team_b = env['sports.team'].create({'name': 'JN Team B'})

    def _patient(self, first, last, team=None, **vals):
        vals.update({'first_name': first, 'last_name': last})
        patient = self.env['sports.patient'].create(vals)
        if team:
            patient.team_ids = [Command.set([team.id])]
        return patient

    # ------------------------------------------------------------------
    # labels
    # ------------------------------------------------------------------
    def test_labels_with_number(self):
        p = self._patient('Émile', 'Tremblay', jersey_number='12')
        self.assertEqual(p._jersey_label(), '#12')
        self.assertEqual(p._portal_list_name(), '#12 Tremblay, Émile')
        self.assertEqual(p._portal_list_name(with_jersey=False), 'Tremblay, Émile')
        self.assertEqual(p._portal_heading_name(), '#12 Émile Tremblay')
        # ``name`` itself (breadcrumbs, chatter) stays « First Last ».
        self.assertEqual(p.name, 'Émile Tremblay')

    def test_labels_without_number_unchanged(self):
        p = self._patient('Émile', 'Tremblay')
        self.assertEqual(p._jersey_label(), '')
        self.assertEqual(p._portal_list_name(), 'Tremblay, Émile')
        self.assertEqual(p._portal_heading_name(), 'Émile Tremblay')
        self.assertNotIn('#', p._portal_list_name())
        self.assertNotIn('#', p._portal_heading_name())

    def test_zero_zero_survives(self):
        p = self._patient('Zed', 'Zero', jersey_number='00')
        self.assertEqual(p.jersey_number, '00')
        self.assertEqual(p._jersey_label(), '#00')

    def test_input_normalised(self):
        p = self._patient('Nora', 'Norm', jersey_number=' #12 ')
        self.assertEqual(p.jersey_number, '12')
        p.write({'jersey_number': '  '})
        self.assertFalse(p.jersey_number)
        self.assertEqual(p._portal_list_name(), 'Norm, Nora')

    def test_combo_key_and_options(self):
        p = self._patient('Zoé', 'Äbel', jersey_number='12')
        key = p._portal_combo_key()
        self.assertTrue(key.startswith('abel zoe'), key)
        # The client-side filter is a substring / word-prefix match on the key:
        # typing « 12 » or « #12 » must find the player.
        self.assertIn('12', key)
        self.assertIn('#12', key)
        q = self._patient('Ana', 'Nuñez')
        self.assertEqual(q._portal_combo_key(), 'nunez ana')
        options = (p + q)._portal_combo_options()
        self.assertEqual([label for _id, label, _key in options],
                         ['#12 Äbel, Zoé', 'Nuñez, Ana'])
        self.assertEqual(options[1], (q.id, 'Nuñez, Ana', 'nunez ana'))

    # ------------------------------------------------------------------
    # sort helper
    # ------------------------------------------------------------------
    def test_jersey_sort_numeric_blanks_last(self):
        ten = self._patient('A', 'Ten', self.team_a, jersey_number='10')
        two = self._patient('B', 'Two', self.team_a, jersey_number='2')
        twelve = self._patient('C', 'Twelve', self.team_a, jersey_number='12')
        blank = self._patient('D', 'Blank', self.team_a)
        zero = self._patient('E', 'Zero', self.team_a, jersey_number='00')
        self.assertEqual(two.jersey_sort, 2)
        self.assertEqual(ten.jersey_sort, 10)
        self.assertGreater(blank.jersey_sort, twelve.jersey_sort)
        ordered = self.env['sports.patient'].search(
            [('team_ids', 'in', [self.team_a.id])], order='jersey_sort, last_name')
        self.assertEqual(ordered, zero + two + ten + twelve + blank)
        # Changing the number moves the row.
        two.jersey_number = '99'
        ordered = self.env['sports.patient'].search(
            [('team_ids', 'in', [self.team_a.id])], order='jersey_sort, last_name')
        self.assertEqual(ordered, zero + ten + twelve + two + blank)

    # ------------------------------------------------------------------
    # duplicates (soft)
    # ------------------------------------------------------------------
    def test_duplicates_shared_team_only(self):
        first = self._patient('First', 'Seven', self.team_a, jersey_number='7')
        other = self._patient('Other', 'Seven', self.team_b, jersey_number='7')
        self.assertFalse(first._jersey_duplicates(), 'unrelated teams: no warning')
        same = self._patient('Same', 'Seven', self.team_a, jersey_number='7')
        self.assertEqual(first._jersey_duplicates(), same)
        self.assertEqual(same._jersey_duplicates(), first)
        self.assertIn('Same Seven', first._jersey_duplicate_message())
        # Archived players never count; blanks never collide.
        same.active = False
        self.assertFalse(first._jersey_duplicates())
        blank_a = self._patient('Blank', 'A', self.team_a)
        blank_b = self._patient('Blank', 'B', self.team_a)
        self.assertFalse(blank_a._jersey_duplicates())
        self.assertFalse(blank_b._jersey_duplicates())
        self.assertFalse(other._jersey_duplicates())

    def test_duplicate_never_blocks(self):
        self._patient('First', 'Nine', self.team_a, jersey_number='9')
        dup = self._patient('Second', 'Nine', self.team_a, jersey_number='9')
        self.assertEqual(dup.jersey_number, '9')
        dup.write({'jersey_number': '9'})
        self.assertEqual(dup.jersey_number, '9')

    # ------------------------------------------------------------------
    # portal create whitelist
    # ------------------------------------------------------------------
    def test_create_portal_patient_keeps_position_and_number(self):
        patient = self.env['sports.patient']._create_portal_patient({
            'first_name': 'Whitelist', 'last_name': 'Fix',
            'position': 'Goalie', 'jersey_number': '31',
            'team_ids': [(6, 0, [self.team_a.id])],
        })
        self.assertEqual(patient.position, 'Goalie')
        self.assertEqual(patient.jersey_number, '31')
        self.assertEqual(patient.team_ids, self.team_a)
        # Blank inputs stay blank (no stray empty string).
        patient2 = self.env['sports.patient']._create_portal_patient({
            'first_name': 'Whitelist', 'last_name': 'Blank',
            'position': '', 'jersey_number': '',
        })
        self.assertFalse(patient2.position)
        self.assertFalse(patient2.jersey_number)

    # ------------------------------------------------------------------
    # digest payload
    # ------------------------------------------------------------------
    def test_digest_payload_carries_number(self):
        patient = self._patient('Digest', 'Player', self.team_a, jersey_number='12')
        self.env.flush_all()
        self.env.cr.precommit.run()
        injury = self.env['sports.patient.injury'].create({
            'patient_id': patient.id, 'diagnosis': 'Sprain'})
        injury.with_context(mail_notrack=True).write({'stage': 'active'})
        self.env.flush_all()
        self.env.cr.precommit.run()
        digest = self.env['sports.team.digest']._capture_team(
            self.team_a, fields.Datetime.now(), fields.Date.today(), 'UTC')
        stored = [p for p in digest.item_data['players'] if p['player_id'] == patient.id]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['jersey_number'], '12')
        self.assertEqual(stored[0]['player_name'], 'Digest Player')
        rendered = digest._render_for_role('tp')
        self.assertEqual([p['jersey_number'] for p in rendered if p['player_id'] == patient.id], ['12'])
        html = digest.with_context(digest_role='tp').digest_html or ''
        self.assertIn('#12', html)

    # ------------------------------------------------------------------
    # backend form (view declares the field)
    # ------------------------------------------------------------------
    def test_backend_form_field(self):
        patient = self._patient('Back', 'End', self.team_a)
        with Form(patient, view='bemade_sports_clinic.sports_patient_view_form') as form:
            form.jersey_number = '#44'
        self.assertEqual(patient.jersey_number, '44')
        list_view = self.env.ref('bemade_sports_clinic.sports_patient_view_list')
        self.assertIn('jersey_number', list_view.arch)
        search_view = self.env.ref('bemade_sports_clinic.sports_patient_view_search')
        self.assertIn('jersey_number', search_view.arch)
        groups = self.env['sports.patient'].read_group(
            [('team_ids', 'in', [self.team_a.id])], ['id:count'], ['jersey_number'])
        self.assertTrue(groups)


@tagged('-at_install', 'post_install')
class TestJerseyNumberPortal(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Team A roster: Pat One (no number) + three numbered players whose
        # alphabetical order differs from the numeric one.
        def _player(first, last, team, number=None):
            p = env['sports.patient'].create({
                'first_name': first, 'last_name': last, 'jersey_number': number})
            p.team_ids = [Command.set([team.id])]
            return p
        cls.ten = _player('Aline', 'Aten', cls.team_a, '10')
        cls.twelve = _player('Bob', 'Btwelve', cls.team_a, '12')
        cls.two = _player('Cleo', 'Ctwo', cls.team_a, '2')
        # Team B: same number as « twelve », on an UNRELATED team.
        cls.twelve_b = _player('Dan', 'Dtwelve', cls.team_b, '12')
        # The coach also staffs team B so both teams are reachable.
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'JN Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.twelve.id})

    def _doc(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)

    @staticmethod
    def _texts(nodes):
        return [' '.join(n.text_content().split()) for n in nodes]

    # ------------------------------------------------------------------
    # AC1 — round trips
    # ------------------------------------------------------------------
    def test_create_as_tp_stores_number_and_position(self):
        self._login_tp()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(),
            'first_name': 'Created', 'last_name': 'Bytp',
            'date_of_birth': '2004-04-04', 'team_ids': self.team_a.id,
            'position': 'Center', 'jersey_number': '#88',
        })
        self.assertEqual(resp.status_code, 200)
        p = self.env['sports.patient'].search([('last_name', '=', 'Bytp')])
        self.assertEqual(len(p), 1)
        self.assertEqual(p.position, 'Center', 'position was silently dropped on create')
        self.assertEqual(p.jersey_number, '88')

    def test_create_as_coach_stores_number(self):
        # A coach-created player has no team (the team block is TP-gated, as
        # before), so the redirect target 403s for the coach: check the record.
        self._login_coach()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(),
            'first_name': 'Created', 'last_name': 'Bycoach',
            'position': 'Wing', 'jersey_number': '5',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        p = self.env['sports.patient'].search([('last_name', '=', 'Bycoach')])
        self.assertEqual(p.jersey_number, '5')
        self.assertEqual(p.position, 'Wing')

    def test_edit_as_coach_and_tp(self):
        self._login_coach()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id, 'first_name': 'Pat', 'last_name': 'One',
            'jersey_number': '21',
        })
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset(['jersey_number'])
        self.assertEqual(self.player.jersey_number, '21')
        self._login_tp()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id, 'first_name': 'Pat', 'last_name': 'One',
            'team_ids': self.team_a.id, 'jersey_number': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset(['jersey_number'])
        self.assertFalse(self.player.jersey_number, 'blank clears the number')

    def test_edit_form_prefills_number(self):
        self._login_coach()
        doc = self._doc('/my/player/edit?patient_id=%s' % self.twelve.id)
        inputs = doc.cssselect('input[name="jersey_number"]')
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].get('value'), '12')
        self.assertEqual(inputs[0].get('maxlength'), '8')

    # ------------------------------------------------------------------
    # AC2 / AC3 — display sites
    # ------------------------------------------------------------------
    def test_players_grid_and_roster_cards(self):
        self._login_tp()
        doc = self._doc('/my/players')
        names = self._texts(doc.cssselect('.card-header a.fw-bold'))
        self.assertIn('#12 Btwelve, Bob', names)
        self.assertIn('#2 Ctwo, Cleo', names)
        self.assertIn('One, Pat', names)
        self.assertFalse([n for n in names if n.startswith('#') and n.endswith(',')], names)
        doc = self._doc('/my/team?team_id=%s' % self.team_a.id)
        names = self._texts(doc.cssselect('#players .card-header a.fw-bold'))
        self.assertIn('#10 Aten, Aline', names)
        self.assertIn('One, Pat', names)

    def test_player_heading_and_dossier(self):
        self._login_tp()
        doc = self._doc('/my/player?player_id=%s' % self.twelve.id)
        self.assertEqual(self._texts(doc.cssselect('h1'))[:1], ['#12 Bob Btwelve'])
        doc = self._doc('/my/player?player_id=%s' % self.player.id)
        self.assertEqual(self._texts(doc.cssselect('h1'))[:1], ['Pat One'])
        # Clinic dossier card + worklist row.
        doc = self._doc('/my/clinic/%s?patient=%s' % (self.clinic.id, self.twelve.id))
        headers = self._texts(doc.cssselect('#clinic-dossier h5'))
        self.assertIn('#12 Bob Btwelve', headers)
        rows = self._texts(doc.cssselect('ul.o_sc_worklist .o_sc_worklist_row a'))
        self.assertEqual(rows, ['#12 Btwelve, Bob'])

    def test_picker_option_label_and_key(self):
        self._login_tp()
        doc = self._doc('/my/clinic/%s' % self.clinic.id)
        select = doc.cssselect('.o_sc_patient_combo > select[name="patient_id"]')[0]
        options = {o.text_content().strip(): o for o in select.iter('option') if o.get('value')}
        self.assertIn('#10 Aten, Aline', options)
        self.assertIn('One, Pat', options)
        key = options['#10 Aten, Aline'].get('data-key')
        self.assertTrue(key.startswith('aten aline'), key)
        self.assertIn('#10', key)
        self.assertEqual(options['One, Pat'].get('data-key'), 'one pat')

    def test_search_results_show_number(self):
        self._login_tp()
        doc = self._doc('/my/player/create?first_name=Bob&last_name=Btwelve')
        labels = self._texts(doc.cssselect('.list-group-item .fw-bold'))
        self.assertIn('#12 Bob Btwelve', labels)
        doc = self._doc('/my/team/%s/player/add_link?first_name=Pat&last_name=One' % self.team_a.id)
        labels = self._texts(doc.cssselect('.list-group-item strong'))
        self.assertIn('Pat One', labels)

    # ------------------------------------------------------------------
    # AC4 — roster sort
    # ------------------------------------------------------------------
    def _roster_names(self, url):
        doc = self._doc(url)
        return self._texts(doc.cssselect('#players .card-header a.fw-bold'))

    def test_roster_sort_by_number_sticky(self):
        self._login_coach()
        base = '/my/team?team_id=%s' % self.team_a.id
        default = self._roster_names(base)
        self.assertEqual(default, ['#10 Aten, Aline', '#12 Btwelve, Bob', '#2 Ctwo, Cleo', 'One, Pat'])
        by_number = self._roster_names(base + '&sort=number')
        self.assertEqual(by_number, ['#2 Ctwo, Cleo', '#10 Aten, Aline', '#12 Btwelve, Bob', 'One, Pat'])
        self.coach.invalidate_recordset(['roster_sort_mode'])
        self.assertEqual(self.coach.roster_sort_mode, 'number')
        # Sticky: the next visit without ?sort keeps the number order.
        self.assertEqual(self._roster_names(base), by_number)
        # Back to the default order, also sticky.
        self.assertEqual(self._roster_names(base + '&sort=status'), default)
        self.coach.invalidate_recordset(['roster_sort_mode'])
        self.assertEqual(self.coach.roster_sort_mode, 'status')
        # Another user is unaffected.
        self.tp.invalidate_recordset(['roster_sort_mode'])
        self.assertFalse(self.tp.roster_sort_mode)

    def test_roster_sort_toggle_rendered_and_tab_active(self):
        self._login_coach()
        doc = self._doc('/my/team?team_id=%s&sort=number' % self.team_a.id)
        links = doc.cssselect('.o_sc_roster_sort a')
        self.assertEqual(len(links), 2)
        hrefs = [a.get('href') for a in links]
        self.assertTrue(any('sort=status' in h for h in hrefs), hrefs)
        self.assertTrue(any('sort=number' in h for h in hrefs), hrefs)
        active = [a for a in links if 'active' in (a.get('class') or '')]
        self.assertEqual(len(active), 1)
        self.assertIn('sort=number', active[0].get('href'))
        # A sort reload lands on the roster tab, not the dashboard.
        players_tab = doc.cssselect('#players-tab')[0]
        self.assertIn('active', players_tab.get('class'))
        self.assertIn('active', doc.cssselect('#players')[0].get('class'))
        self.assertNotIn('active', doc.cssselect('#dashboard-tab')[0].get('class'))

    # ------------------------------------------------------------------
    # AC5 — duplicate warning
    # ------------------------------------------------------------------
    def test_duplicate_warning_shared_team(self):
        self._login_coach()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player.id, 'first_name': 'Pat', 'last_name': 'One',
            'jersey_number': '12',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        location = resp.headers.get('Location', '')
        self.assertIn('warning=duplicate_number', location)
        self.player.invalidate_recordset(['jersey_number'])
        self.assertEqual(self.player.jersey_number, '12', 'the save still succeeds')
        doc = self._doc(location)
        alerts = self._texts(doc.cssselect('.alert-warning.o_sc_jersey_warning'))
        self.assertEqual(len(alerts), 1)
        self.assertIn('Bob Btwelve', alerts[0])
        self.assertIn('#12', alerts[0])
        # Dan Dtwelve (team B) is NOT a shared-team duplicate.
        self.assertNotIn('Dtwelve', alerts[0])

    def test_no_warning_across_unrelated_teams(self):
        self._login_tp()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(),
            'patient_id': self.player_b.id, 'first_name': 'Pat', 'last_name': 'Two',
            'team_ids': self.team_b.id, 'jersey_number': '10',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn('warning=', resp.headers.get('Location', ''))
        self.player_b.invalidate_recordset(['jersey_number'])
        self.assertEqual(self.player_b.jersey_number, '10')
        doc = self._doc('/my/player?player_id=%s' % self.player_b.id)
        self.assertEqual(doc.cssselect('.o_sc_jersey_warning'), [])

    def test_warning_param_without_duplicate_is_silent(self):
        self._login_tp()
        doc = self._doc('/my/player?player_id=%s&warning=duplicate_number' % self.player.id)
        self.assertEqual(doc.cssselect('.o_sc_jersey_warning'), [])

    def test_create_duplicate_warning(self):
        self._login_tp()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(),
            'first_name': 'Dup', 'last_name': 'Ten',
            'date_of_birth': '2004-04-04', 'team_ids': self.team_a.id,
            'jersey_number': '10',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('warning=duplicate_number', resp.headers.get('Location', ''))

    # ------------------------------------------------------------------
    # AC2 — /my/players jersey filter
    # ------------------------------------------------------------------
    def test_players_jersey_filter(self):
        self._login_tp()
        doc = self._doc('/my/players?jersey_number=12')
        names = self._texts(doc.cssselect('.card-header a.fw-bold, .card-header span.fw-bold'))
        self.assertIn('#12 Btwelve, Bob', names)
        self.assertIn('#12 Dtwelve, Dan', names)
        self.assertNotIn('#10 Aten, Aline', names)
        self.assertNotIn('One, Pat', names)
        inputs = doc.cssselect('input[name="jersey_number"]')
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].get('value'), '12')
        # « #12 » works too, and a non-matching number yields an empty list.
        doc = self._doc('/my/players?jersey_number=%2312')
        self.assertIn('#12 Btwelve, Bob',
                      self._texts(doc.cssselect('.card-header a.fw-bold, .card-header span.fw-bold')))
        doc = self._doc('/my/players?jersey_number=77')
        self.assertEqual(doc.cssselect('.card-header a.fw-bold'), [])
