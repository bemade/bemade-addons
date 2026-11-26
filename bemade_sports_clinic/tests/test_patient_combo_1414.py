"""Task 1414 — portal-wide patient selector: « Last, First » read and sorted
from the patient record (last_name / first_name), the reusable
portal_patient_combo snippet behind every patient picker, and the portal
lists (clinic worklist) reading « Last, First » while single-patient
headings keep « First Last ».

Covered here (synthetic fixtures — this addon's repository is public):

* sports.patient._portal_list_name / _portal_combo_key / _portal_combo_sorted
  / _portal_combo_options: format, graceful on a missing part, accent and
  case insensitive ordering (« abel » < « Abel » < « Äbel » only by first
  name, « Zamora » last);
* the clinic add-patient picker: rendered by the snippet (.o_sc_patient_combo
  wrapper, real <select name="patient_id">, data-key on the options), the
  two optgroups kept in order, options « Last, First » sorted by last name —
  no longer res.partner.name order;
* the quick-note create + edit-row pickers: same snippet, same order, the
  edit row preselects the note's player;
* the clinic worklist rows (page + fragment) read « Last, First »; the
  dossier header and the player page H1 keep « First Last »; /my/players
  cards keep « Last, First »;
* JS absent: the plain select posts — adding a patient to the worklist and
  linking a quick note work with the select's value exactly as before.

NOT claimed: the browser behaviour of the combo (filtering, keyboard,
touch, « × », the no-JS look). That is the /dev-review click-through.
"""
import re
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestPatientCombo1414(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'PC Org', 'is_company': True})
        cls.team_a = env['sports.team'].create({'name': 'PC Team A', 'parent_id': cls.org.id})
        cls.team_b = env['sports.team'].create({'name': 'PC Team B', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Pia Therapist', 'login': 'pc.tp@example.com', 'password': 'pc-tp-pass',
            'group_ids': [Command.set([portal_g, tp_g])],
        })
        for team in (cls.team_a, cls.team_b):
            env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
            })

        def _patient(first, last, team):
            patient = env['sports.patient'].create({'first_name': first, 'last_name': last})
            patient.team_ids = [Command.set([team.id])]
            return patient

        # Team A (the clinic's team): partner names « First Last » would sort
        # Émile < Marc < Zoé < anna; « Last, First » must give
        # abel, anna / Abel, Émile / Äbel, Zoé / Zamora, Marc.
        cls.zoe = _patient('Zoé', 'Äbel', cls.team_a)
        cls.emile = _patient('Émile', 'Abel', cls.team_a)
        cls.anna = _patient('anna', 'abel', cls.team_a)
        cls.marc = _patient('Marc', 'Zamora', cls.team_a)
        # Team B (« Other teams » group).
        cls.bea = _patient('Bea', 'Ortiz', cls.team_b)
        cls.ana = _patient('Ana', 'Nuñez', cls.team_b)

        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'PC Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        # Zoé is already on the worklist: she must NOT be offered by the picker.
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.zoe.id})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _login(self):
        self.authenticate('pc.tp@example.com', 'pc-tp-pass')

    def _csrf(self):
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    def _doc(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)

    def _select(self, doc, name, index=0):
        selects = doc.cssselect('.o_sc_patient_combo > select[name="%s"]' % name)
        self.assertGreater(len(selects), index, 'combo select %s not rendered' % name)
        return selects[index]

    @staticmethod
    def _labels(node):
        return [o.text_content().strip() for o in node.findall('option') if o.get('value')]

    # ==================================================================
    # model helpers
    # ==================================================================
    def test_list_name_last_first(self):
        self.assertEqual(self.zoe._portal_list_name(), 'Äbel, Zoé')
        self.assertEqual(self.ana._portal_list_name(), 'Nuñez, Ana')
        # Single-patient surfaces keep « First Last ».
        self.assertEqual(self.zoe.name, 'Zoé Äbel')

    def test_list_name_graceful_on_missing_part(self):
        Patient = self.env['sports.patient']
        self.assertEqual(Patient.new({'last_name': 'Solo', 'first_name': ''})._portal_list_name(), 'Solo')
        self.assertEqual(Patient.new({'last_name': '', 'first_name': 'Zoé'})._portal_list_name(), 'Zoé')
        self.assertEqual(Patient.new({'last_name': ' Solo ', 'first_name': ' Zoé '})._portal_list_name(), 'Solo, Zoé')

    def test_name_key_accent_and_case_insensitive(self):
        Patient = self.env['sports.patient']
        self.assertEqual(Patient._portal_name_key('Zoé  Äbel'), 'zoe abel')
        self.assertEqual(Patient._portal_name_key('  NUÑEZ '), 'nunez')
        self.assertEqual(Patient._portal_name_key(False), '')
        self.assertEqual(self.zoe._portal_combo_key(), 'abel zoe')
        self.assertEqual(self.ana._portal_combo_key(), 'nunez ana')

    def test_combo_sorted_and_options(self):
        # Arbitrary incoming order (res.partner.name order, which the old
        # clinic picker used): Émile Abel, Marc Zamora, Zoé Äbel, anna abel.
        mixed = self.emile + self.marc + self.zoe + self.anna
        self.assertEqual(mixed._portal_combo_sorted(), self.anna + self.emile + self.zoe + self.marc)
        options = mixed._portal_combo_options()
        self.assertEqual(
            [label for _id, label, _key in options],
            ['abel, anna', 'Abel, Émile', 'Äbel, Zoé', 'Zamora, Marc'])
        self.assertEqual(options[0], (self.anna.id, 'abel, anna', 'abel anna'))
        self.assertEqual(self.env['sports.patient']._portal_combo_options(), [])


    def test_clinic_picker_no_other_group_when_empty(self):
        # A therapist staffed on the clinic's team only: no « Other teams » group.
        self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_b.id), ('partner_id', '=', self.tp.partner_id.id)]).unlink()
        self._login()
        doc = self._doc('/my/clinic/%s' % self.clinic.id)
        select = self._select(doc, 'patient_id')
        self.assertEqual([g.get('label') for g in select.findall('optgroup')], ['Clinic teams'])

    def test_clinic_add_posts_plain_select_value(self):
        self._login()
        token = self._csrf()
        resp = self.url_open('/my/clinic/%s/attendance/add' % self.clinic.id,
                             data={'csrf_token': token, 'patient_id': str(self.anna.id)},
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('success=patient_added', resp.headers.get('Location', ''))
        self.assertTrue(self.env['sports.clinic.attendance'].sudo().search_count([
            ('event_id', '=', self.clinic.id), ('patient_id', '=', self.anna.id)]))
        # … and the picker no longer offers her.
        doc = self._doc('/my/clinic/%s' % self.clinic.id)
        groups = self._select(doc, 'patient_id').findall('optgroup')
        self.assertEqual(self._labels(groups[0]), ['Abel, Émile', 'Zamora, Marc'])


    def test_quick_note_add_posts_plain_select_value(self):
        self._login()
        token = self._csrf()
        resp = self.url_open('/my/notepad/add', data={
            'csrf_token': token, 'note': 'Synthetic posted note',
            'patient_id': str(self.ana.id),
        })
        self.assertEqual(resp.status_code, 200)
        note = self.env['sports.quick.note'].sudo().search(
            [('note', '=', 'Synthetic posted note')], limit=1)
        self.assertTrue(note)
        self.assertEqual(note.patient_id, self.ana)


