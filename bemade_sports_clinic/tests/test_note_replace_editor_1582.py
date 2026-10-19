"""Task 1582 — injury notes: therapists append instead of replacing. The two
injury notes stay ONE « current state » text each (every version kept in
sports.injury.note.history); the app's note editor becomes a « replace »
editor. Server side of it. Synthetic fixtures only (public repo).

Acceptance criteria covered here:

* UC-R1 The injury page edits both notes with the opt-in replace editor
  (``replace`` prop, the « Write the injury's current state … » placeholder)
  and a « History » link on each field opening a SCOPED history sheet
  (external for the external note, internal for the internal one). A coach
  gets the external note only, and no internal sheet.
* UC-R2 The player page's inline injury card does the same, per injury.
* UC-R3 Every other autosave field is unchanged: no ``replace`` prop
  (diagnosis, dates, status, training recommendation…).
* UC-R4 A save through the route still REPLACES the text and adds ONE
  history row (the editor's save path is unchanged).
* UC-R5 Recent changes / digests: a note change renders as the NEW text
  only, flagged « New note » — never old → new — while another tracked field
  of the same injury keeps its old → new rendering. A stored digest snapshot
  carrying an old value for a note (defensive) still renders the new text
  only.
* UC-R6 Wording: the backend form and the legacy portal edit forms show the
  « Current state (replaces the previous text; …) » placeholder, and both
  fields carry it as their help.
* UC-R7 Every new string renders in French (fr_CA): the OWL editor's
  (« Texte actuel », « Nouvelle note », « Reprendre le texte actuel »,
  « Remplace le texte précédent ; l'ancien est conservé dans
  l'historique. ») served by the translations route, the page's placeholder
  / sheet titles / « Historique », the digest's « Nouvelle note », the
  legacy placeholder « État actuel (…) ».
"""
import json
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

PLACEHOLDER = "Write the injury's current state — replaces the previous text"
HELP = "Current state (replaces the previous text; the history keeps the versions)"
NOTE_FIELDS = ('external_notes', 'internal_notes')


def _autosave_props(node):
    out = {}
    for raw in node.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props'):
        props = json.loads(raw)
        out[props.get('field') or props.get('name')] = props
    return out


@tagged('post_install', '-at_install')
class TestNoteReplaceEditor1582(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.sudo().write({
            'external_notes': 'T1582 synthetic external v1',
            'internal_notes': 'T1582 synthetic internal v1',
        })
        cls.edit_url = '/my/injury/edit?injury_id=%s' % cls.injury.id

    def _sheet(self, tree, sheet_id):
        nodes = tree.xpath('//dialog[@id="%s"]' % sheet_id)
        return nodes[0] if nodes else None

    # -- UC-R1 -----------------------------------------------------------
    def test_injury_page_notes_use_replace_editor_tp(self):
        self._login_tp()
        _text, tree = self._get(self.edit_url)
        props = _autosave_props(tree)
        for fname, scope in (('external_notes', 'external'), ('internal_notes', 'internal')):
            with self.subTest(field=fname):
                self.assertIs(props[fname].get('replace'), True)
                self.assertEqual(props[fname]['inputType'], 'textarea')
                self.assertEqual(props[fname]['placeholder'], PLACEHOLDER)
                # Task 1616: the injury page is the open card (per-injury ids).
                self.assertEqual(props[fname]['historySheet'],
                                 'sc_note_history_sheet_%s_%s' % (self.injury.id, scope))
                self.assertEqual(props[fname]['historyLabel'], 'History')
                # The current text is the value the editor shows read-only.
                self.assertEqual(props[fname]['value'], 'T1582 synthetic %s v1' % scope)
                sheet = self._sheet(tree, 'sc_note_history_sheet_%s_%s' % (self.injury.id, scope))
                self.assertIsNotNone(sheet)
                self.assertTrue(sheet.get('data-sc-lazy-url').endswith(
                    '/my/injury/%s/notes/history/fragment?scope=%s' % (self.injury.id, scope)))
        # The all-scopes sheet of the card header is kept (task 1581).
        self.assertIsNotNone(self._sheet(tree, 'sc_note_history_sheet_%s' % self.injury.id))

    def test_injury_page_coach_external_only(self):
        self._login_coach()
        _text, tree = self._get(self.edit_url)
        props = _autosave_props(tree)
        self.assertIs(props['external_notes'].get('replace'), True)
        self.assertNotIn('internal_notes', props)
        self.assertIsNotNone(self._sheet(tree, 'sc_note_history_sheet_%s_external' % self.injury.id))
        self.assertIsNone(self._sheet(tree, 'sc_note_history_sheet_%s_internal' % self.injury.id))

    def test_scoped_history_fragment(self):
        self._login_tp()
        self.injury.sudo().write({'external_notes': 'T1582 synthetic external v2'})
        _text, tree = self._get(
            '/my/injury/%s/notes/history/fragment?scope=external' % self.injury.id)
        scopes = set(tree.xpath('//li[contains(@class, "o_sc_history_entry")]/@data-sc-scope'))
        self.assertEqual(scopes, {'external'})

    # -- UC-R2 -----------------------------------------------------------
    def test_player_inline_card_uses_replace_editor(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='injuries', team_id=self.team_a.id))
        item = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        props = _autosave_props(item)
        for fname, scope in (('external_notes', 'external'), ('internal_notes', 'internal')):
            with self.subTest(field=fname):
                sheet_id = 'sc_note_history_sheet_%s_%s' % (self.injury.id, scope)
                self.assertIs(props[fname].get('replace'), True)
                self.assertEqual(props[fname]['historySheet'], sheet_id)
                sheet = self._sheet(item, sheet_id)
                self.assertIsNotNone(sheet)
                self.assertTrue(sheet.get('data-sc-lazy-url').endswith('?scope=%s' % scope))

    def test_player_inline_card_coach(self):
        self._login_coach()
        _text, tree = self._get(self._url(tab='injuries', team_id=self.team_a.id))
        item = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        props = _autosave_props(item)
        self.assertIs(props['external_notes'].get('replace'), True)
        self.assertNotIn('internal_notes', props)
        self.assertIsNone(self._sheet(item, 'sc_note_history_sheet_%s_internal' % self.injury.id))

    # -- UC-R3 -----------------------------------------------------------
    def test_other_autosave_fields_unchanged(self):
        self._login_tp()
        pages = [self.edit_url, self._url(tab='injuries', team_id=self.team_a.id),
                 self._url(tab='info', team_id=self.team_a.id)]
        seen = set()
        for url in pages:
            _text, tree = self._get(url)
            for fname, props in _autosave_props(tree).items():
                seen.add(fname)
                if fname not in NOTE_FIELDS:
                    self.assertNotIn('replace', props, '%s on %s' % (fname, url))
        # The check did look at other fields.
        self.assertTrue({'diagnosis', 'stage'} & seen)

    # -- UC-R4 -----------------------------------------------------------
    def test_save_replaces_and_adds_one_history_row(self):
        self._login_tp()
        History = self.env['sports.injury.note.history']
        before = History.search_count([('injury_id', '=', self.injury.id), ('scope', '=', 'external')])
        resp = self._save(self.injury, 'external_notes', 'T1582 synthetic external v2')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'T1582 synthetic external v2')
        rows = History.search([('injury_id', '=', self.injury.id), ('scope', '=', 'external')])
        self.assertEqual(len(rows), before + 1)
        self.assertIn('T1582 synthetic external v2', rows.mapped('content'))
        # The answer carries the refreshed « Last note on … by … » stamp
        # (task 1601) the replace editor shows under the current text.
        self.assertTrue(resp.json().get('hint'))

    # -- UC-R6 -----------------------------------------------------------
    def test_legacy_edit_form_placeholder(self):
        self._switch(False)
        self._login_tp()
        _text, tree = self._get(self.edit_url)
        for fname in NOTE_FIELDS:
            area = tree.xpath('//textarea[@name="%s"]' % fname)
            self.assertTrue(area, fname)
            self.assertEqual(area[0].get('placeholder'), HELP)


@tagged('post_install', '-at_install')
class TestNoteChangeRender1582(TransactionCase):
    """UC-R5 / UC-R6 (backend)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tp_group = cls.env.ref("bemade_sports_clinic.group_sports_clinic_treatment_professional")
        cls.env.user.sudo().group_ids = [Command.link(tp_group.id)]
        org = cls.env["res.partner"].create({"name": "T1582 Org", "is_company": True})
        cls.team = cls.env["sports.team"].create({"name": "T1582 Team", "parent_id": org.id})

    def _settle(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _render(self, items):
        html = self.env["ir.qweb"]._render(
            "bemade_sports_clinic.dashboard_change_items", {"items": items})
        return str(html)

    def _changed_injury(self):
        patient = self.env["sports.patient"].create({
            "first_name": "Zz", "last_name": "Synthetic",
            "team_ids": [Command.link(self.team.id)],
        })
        injury = self.env["sports.patient.injury"].create({
            "patient_id": patient.id, "diagnosis": "T1582 dx old",
            "external_notes": "T1582 OLD external text",
        })
        self._settle()
        when = fields.Datetime.now() - timedelta(hours=48)
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE id=%s", (when, injury.id))
        self.env.cr.execute(
            "UPDATE sports_injury_note_history SET note_datetime=%s WHERE injury_id=%s",
            (when, injury.id))
        injury.invalidate_recordset()
        injury.write({"diagnosis": "T1582 dx new", "external_notes": "T1582 NEW external text"})
        self._settle()
        return patient, injury

    def test_note_change_is_new_text_only(self):
        patient, _injury = self._changed_injury()
        items = patient._dashboard_change_items("tp")
        note = next(it for it in items if it["category"] == "note")
        self.assertEqual(note["field"], "external_notes")
        self.assertEqual(note["value"], "T1582 NEW external text")
        self.assertFalse(note["old_value"])
        diag = next(it for it in items if it["field"] == "diagnosis")
        self.assertEqual(diag["old_value"], "T1582 dx old")

        out = self._render(items)
        tree = lxml_html.fromstring(out)
        self.assertIn("T1582 NEW external text", out)
        self.assertNotIn("T1582 OLD external text", out)
        self.assertEqual(len(tree.xpath('//*[contains(@class, "dashboard-digest-new-note")]')), 1)
        self.assertIn("New note", out)
        # The other tracked field keeps old → new.
        struck = tree.xpath('//*[contains(@class, "text-decoration-line-through")]/text()')
        self.assertEqual(struck, ["T1582 dx old"])

    def test_snapshot_note_with_old_value_renders_new_text_only(self):
        # A stored digest snapshot is a plain dict; even one carrying an old
        # value for a note (defensive) renders the new text alone.
        items = [{
            "category": "note", "field": "internal_notes", "label": "Internal Notes",
            "value": "T1582 snap new", "old_value": "T1582 snap old", "preview": "T1582 snap new",
            "is_long": False, "icon": "fa-sticky-note", "injury_diagnosis": "T1582 dx",
        }, {
            "category": "injury", "field": "diagnosis", "label": "Diagnosis",
            "value": "T1582 dx b", "old_value": "T1582 dx a", "preview": "T1582 dx b",
            "is_long": False, "icon": "fa-medkit", "injury_diagnosis": "T1582 dx b",
        }]
        out = self._render(items)
        self.assertIn("T1582 snap new", out)
        self.assertNotIn("T1582 snap old", out)
        self.assertIn("T1582 dx a", out)

    def test_backend_wording(self):
        Injury = self.env["sports.patient.injury"]
        for fname in NOTE_FIELDS:
            self.assertEqual(Injury._fields[fname].help, HELP)
        arch = self.env.ref("bemade_sports_clinic.sports_patient_injury_view_form").arch
        for fname in NOTE_FIELDS:
            self.assertIn('<field name="%s" placeholder="%s"/>' % (fname, HELP), arch)


@tagged('post_install', '-at_install')
class TestNoteReplaceFr1582(TestAppShellI18n1538):
    """UC-R7."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def _text(self, url):
        return self._fr(url).replace('&#39;', "'")

    def test_owl_strings_served_in_french(self):
        resp = self.url_open('/web/webclient/translations?lang=fr_CA&mods=bemade_sports_clinic')
        messages = {
            m['id']: m['string']
            for m in resp.json()['modules']['bemade_sports_clinic']['messages']}
        for source, french in (
                ('Current text', 'Texte actuel'),
                ('New note', 'Nouvelle note'),
                ('Reuse current text', 'Reprendre le texte actuel'),
                ('Replaces the previous text; the old one is kept in the history.',
                 "Remplace le texte précédent ; l'ancien est conservé dans l'historique.")):
            self.assertEqual(messages.get(source), french, source)

    def test_injury_page_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/injury/edit?injury_id=%s' % self.injury.id)
        tree = lxml_html.fromstring(text)
        props = _autosave_props(tree)
        self.assertEqual(props['external_notes']['placeholder'],
                         "Écrire l'état actuel de la blessure — remplace le texte précédent")
        self.assertEqual(props['internal_notes']['historyLabel'], 'Historique')
        titles = {t.strip() for t in tree.xpath('//dialog//h2[contains(@class, "o_sc_sheet_title")]/text()')}
        self.assertIn('Historique des notes externes', titles)
        self.assertIn('Historique des notes internes', titles)

    def test_legacy_placeholder_and_digest_in_french(self):
        self._switch(False)
        self._login_tp()
        text = self._text('/my/injury/edit?injury_id=%s' % self.injury.id)
        self.assertIn("État actuel (remplace le texte précédent; l'historique conserve les versions)", text)
        out = str(self.env['ir.qweb'].with_context(lang='fr_CA')._render(
            'bemade_sports_clinic.dashboard_change_items', {'items': [{
                'category': 'note', 'field': 'external_notes', 'label': 'Notes externes',
                'value': 'T1582 fr', 'old_value': '', 'preview': 'T1582 fr', 'is_long': False,
                'icon': 'fa-sticky-note', 'injury_diagnosis': 'T1582 dx'}]}))
        self.assertIn('Nouvelle note', out)
