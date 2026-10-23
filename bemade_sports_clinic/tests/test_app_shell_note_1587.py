"""Task 1587 — a treatment note's pencil edit changes its date and its
linked injury (gap G4 of the app-shell audit). Synthetic fixtures only.

Acceptance criteria:

* UC-N1 The author (or a clinic admin) saves the note's DATE through
  ``/my/app/save``; the answer carries the formatted date.
* UC-N2 The author links the note to another injury OF THE SAME PLAYER, or
  sets it back to a general note (empty value); the answer's display reads
  the diagnosis, or « General note » when empty.
* UC-N3 An injury of ANOTHER player is refused (400, « The selected injury
  does not belong to this player. ») and nothing is written.
* UC-N4 Another therapist (not the author) and a coach are refused (403) —
  for the date and the injury alike.
* UC-N5 The note card's pencil edit holds three fields — note, date,
  injury — the injury a select offering « General note », the player's
  open injuries and the note's current injury (even resolved); the card
  reloads on « Done » so its meta line (date, injury link) is fresh.
* UC-N7 fr_CA: the card reads « Note générale », the injury select offers
  « Note générale », a foreign injury is refused in French.
* UC-N6 (browser tour, phone width) pencil a note -> change its date and
  injury -> « Done » -> the meta line shows the new injury.
"""
import json

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _Note1587Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1587 Second TP', 'login': 't1587.tp2@example.com',
            'password': 't1587-tp2-pass', 'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id,
            'role': 'therapist',
        })
        Injury = env['sports.patient.injury']
        cls.injury2 = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic strain'})
        cls.resolved = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic old bruise'})
        cls.resolved.with_context(mail_notrack=True).write({
            'stage': 'resolved', 'resolution_date': '2025-12-01'})
        cls.closed_other = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic healed cut'})
        cls.closed_other.with_context(mail_notrack=True).write({
            'stage': 'resolved', 'resolution_date': '2025-11-01'})
        cls.foreign = Injury.create({'patient_id': cls.player_b.id, 'diagnosis': 'Synthetic foreign'})
        cls.note = env['sports.treatment.note'].create({
            'patient_id': cls.player.id, 'note': 'Synthetic 1587 note', 'user_id': cls.tp.id,
            'date': '2026-01-10', 'injury_id': cls.resolved.id,
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _wd(self, record):
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _save(self, record, field, value):
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'write_date': self._wd(record),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)



@tagged('post_install', '-at_install')
class TestAppShellNote1587(_Note1587Common):

    # -- UC-N1 -----------------------------------------------------------
    def test_author_saves_date(self):
        self._login_tp()
        resp = self._save(self.note, 'date', '2026-02-14')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['value'], '2026-02-14')
        self.assertTrue(resp.json()['display'])
        self.note.invalidate_recordset()
        self.assertEqual(fields.Date.to_string(self.note.date), '2026-02-14')
        resp = self._save(self.note, 'date', '')
        self.assertEqual(resp.status_code, 400)

    # -- UC-N2 -----------------------------------------------------------
    def test_author_relinks_and_clears_injury(self):
        self._login_tp()
        resp = self._save(self.note, 'injury_id', str(self.injury2.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(str(resp.json()['value']), str(self.injury2.id))
        self.assertEqual(resp.json()['display'], 'Synthetic strain')
        self.note.invalidate_recordset()
        self.assertEqual(self.note.injury_id, self.injury2)
        resp = self._save(self.note, 'injury_id', '')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['display'], 'General note')
        self.note.invalidate_recordset()
        self.assertFalse(self.note.injury_id)
        self.assertEqual(self.note.note_type, 'general')

    # -- UC-N3 -----------------------------------------------------------
    def test_foreign_injury_refused(self):
        self._login_tp()
        resp = self._save(self.note, 'injury_id', str(self.foreign.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('does not belong to this player', resp.json()['message'])
        resp = self._save(self.note, 'injury_id', 'not-an-id')
        self.assertEqual(resp.status_code, 400)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.injury_id, self.resolved)

    # -- UC-N4 -----------------------------------------------------------
    def test_non_author_refused(self):
        self.authenticate('t1587.tp2@example.com', 't1587-tp2-pass')
        self.assertEqual(self._save(self.note, 'date', '2026-03-01').status_code, 403)
        self.assertEqual(self._save(self.note, 'injury_id', '').status_code, 403)
        self._login_coach()
        self.assertEqual(self._save(self.note, 'date', '2026-03-01').status_code, 403)
        self.assertEqual(self._save(self.note, 'injury_id', '').status_code, 403)
        self.note.invalidate_recordset()
        self.assertEqual(fields.Date.to_string(self.note.date), '2026-01-10')
        self.assertEqual(self.note.injury_id, self.resolved)

    # -- UC-N5 -----------------------------------------------------------
    def _note_card_fields(self, url):
        _text, tree = self._get(url)
        cards = tree.xpath('//*[@data-sc-edit-card="note-%s"]' % self.note.id)
        self.assertEqual(len(cards), 1, url)
        card = cards[0]
        # Task 1611: no reload on « Done » — the meta line is a read fragment.
        self.assertIsNone(card.get('data-sc-edit-reload'), url)
        self.assertTrue(card.xpath('.//*[@data-sc-fragment="sports.treatment.note:%s:meta"]' % self.note.id), url)
        edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        props = [json.loads(p) for p in edit.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]
        return {p['field']: p for p in props}, card

    def test_note_card_fields(self):
        self._login_tp()
        for url in ('/my/player?player_id=%s&tab=notes' % self.player.id,
                    '/my/patient/notes?patient_id=%s' % self.player.id):
            by_field, card = self._note_card_fields(url)
            self.assertEqual(set(by_field), {'note', 'date', 'injury_id'}, url)
            self.assertEqual(by_field['date']['inputType'], 'date')
            self.assertEqual(by_field['date']['value'], '2026-01-10')
            injury = by_field['injury_id']
            self.assertEqual(injury['inputType'], 'select')
            self.assertEqual(str(injury['value']), str(self.resolved.id))
            keys = [opt[0] for opt in injury['options']]
            self.assertEqual(keys[0], '')
            self.assertEqual(injury['options'][0][1], 'General note')
            self.assertIn(str(self.injury.id), keys)
            self.assertIn(str(self.injury2.id), keys)
            # The note's current (resolved) injury stays offered; another
            # resolved injury and another player's are not.
            self.assertIn(str(self.resolved.id), keys)
            self.assertNotIn(str(self.closed_other.id), keys)
            self.assertNotIn(str(self.foreign.id), keys)
            self.assertIn('Synthetic old bruise', card.text_content())


@tagged('post_install', '-at_install')
class TestAppShellNoteTour1587(_Note1587Common):
    """UC-N6 (browser, phone width): pencil a note -> change its date and
    its injury -> « Done » reloads the card, the meta line shows the new
    injury; both values are stored."""
    browser_size = '390x844'

    def test_note_date_injury_tour(self):
        self.start_tour('/my/player?player_id=%s&tab=notes' % self.player.id,
                        'sc_1587_note_date_injury', login='pc.tp@example.com')
        self.note.invalidate_recordset()
        self.assertEqual(fields.Date.to_string(self.note.date), '2026-02-14')
        self.assertEqual(self.note.injury_id, self.injury2)


@tagged('post_install', '-at_install')
class TestAppShellNoteFr1587(_Note1587Common):
    """UC-N7 — rendered and answered in fr_CA (website-aware)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.sudo().write({'lang': 'fr_CA'})
        cls.note.sudo().write({'injury_id': False})

    def test_fr_ca(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text, tree = self._get('/my/player?player_id=%s&tab=notes' % self.player.id)
        card = tree.xpath('//*[@data-sc-edit-card="note-%s"]' % self.note.id)[0]
        self.assertIn('Note générale', card.xpath('.//*[contains(@class, "o_sc_note_meta")]')[0].text_content())
        props = {p['field']: p for p in (json.loads(raw) for raw in card.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props'))}
        self.assertEqual(props['injury_id']['options'][0], ['', 'Note générale'])
        self.assertEqual(props['injury_id']['label'], 'Blessure')
        resp = self._save(self.note, 'injury_id', str(self.foreign.id))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], "La blessure choisie n'appartient pas à ce joueur.")
