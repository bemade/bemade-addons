"""Audited followup-note history on patient injuries (task 1241).

Acceptance criteria:
- Writing a new internal_notes value on an injury creates exactly one
  sports.injury.note.history row with scope 'internal', the authenticated
  user as author and the NEW value as content; same for external_notes with
  scope 'external'.
- A save that does not change the note fields creates NO history row, and
  writes to unrelated fields create NO history row.
- History rows are never mutated: rewriting a note creates a second row and
  the earlier row keeps its original content.
- Capture still happens under the mail suppression contexts
  (mail_notrack / mail_create_nosubscribe); only the explicit
  skip_note_history context disables it.
- Creating an injury with initially non-empty notes seeds one row per
  non-empty note field.
- Portal: a coach sees EXTERNAL rows only — both at the record-rule level
  (ORM search) and over HTTP, including when tampering with the scope GET
  parameter; a treatment professional sees both scopes; a portal user with
  no right to the injury gets 403.
- The portal save flow (injury.sudo().write) credits the authenticated
  session user as author, not the superuser.
"""
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestInjuryNoteHistory(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.History = cls.env['sports.injury.note.history']

    def _new_injury(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'team_id': self.team_a.id,
            'diagnosis': 'History Fixture',
        })
        return injury

    def _rows(self, injury, scope=None, order='id asc'):
        domain = [('injury_id', '=', injury.id)]
        if scope:
            domain.append(('scope', '=', scope))
        return self.History.search(domain, order=order)

    # ---- capture on write ----

    def test_internal_change_creates_row(self):
        injury = self._new_injury()
        injury.with_user(self.tp).with_context(mail_notrack=True).write({
            'internal_notes': 'First internal note',
        })
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, 'First internal note')
        self.assertEqual(rows.scope, 'internal')
        self.assertEqual(rows.author_id, self.tp)
        self.assertTrue(rows.note_datetime)
        self.assertEqual(rows.patient_id, self.player)

    def test_external_change_creates_row(self):
        injury = self._new_injury()
        injury.with_user(self.tp).with_context(mail_notrack=True).write({
            'external_notes': 'First external note',
        })
        rows = self._rows(injury, scope='external')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, 'First external note')
        self.assertEqual(rows.author_id, self.tp)

    def test_no_row_when_note_unchanged(self):
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'Same'})
        before = len(self._rows(injury))
        # Re-saving the identical value must not create a row.
        injury.with_context(mail_notrack=True).write({'internal_notes': 'Same'})
        # Neither must a save where the field is present but empty on both sides.
        injury.with_context(mail_notrack=True).write({'external_notes': False})
        self.assertEqual(len(self._rows(injury)), before)

    def test_no_row_on_unrelated_write(self):
        injury = self._new_injury()
        before = len(self._rows(injury))
        injury.with_context(mail_notrack=True).write({
            'diagnosis': 'Changed diagnosis',
            'predicted_resolution_date': '2026-08-01',
        })
        self.assertEqual(len(self._rows(injury)), before)

    def test_rows_are_append_only(self):
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'v1'})
        injury.with_context(mail_notrack=True).write({'internal_notes': 'v2'})
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.mapped('content'), ['v1', 'v2'],
                         "the first snapshot must keep its original content")
        # Default _order surfaces the newest snapshot first.
        ordered = self._rows(injury, scope='internal', order=None)
        self.assertEqual(ordered[0].content, 'v2')

    def test_skip_note_history_context(self):
        injury = self._new_injury()
        injury.with_context(mail_notrack=True, skip_note_history=True).write({
            'internal_notes': 'Invisible to audit',
        })
        self.assertFalse(self._rows(injury))

    # ---- capture on create ----

    def test_create_seeds_initial_notes(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'team_id': self.team_a.id,
            'diagnosis': 'Created with notes',
            'internal_notes': 'Initial internal',
            'external_notes': 'Initial external',
        })
        internal = self._rows(injury, scope='internal')
        external = self._rows(injury, scope='external')
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal.content, 'Initial internal')
        self.assertEqual(len(external), 1)
        self.assertEqual(external.content, 'Initial external')

    def test_create_without_notes_seeds_nothing(self):
        injury = self._new_injury()
        self.assertFalse(self._rows(injury))

    # ---- record rules ----

    def test_coach_record_rule_hides_internal(self):
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'Secret'})
        injury.with_context(mail_notrack=True).write({'external_notes': 'Public'})
        coach_rows = self.History.with_user(self.coach).search(
            [('injury_id', '=', injury.id)])
        self.assertTrue(coach_rows, "coach must see the external row")
        self.assertEqual(set(coach_rows.mapped('scope')), {'external'})
        tp_rows = self.History.with_user(self.tp).search(
            [('injury_id', '=', injury.id)])
        self.assertEqual(set(tp_rows.mapped('scope')), {'internal', 'external'})

    # ---- portal route ----

    def _seed_http_fixture(self):
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write(
            {'internal_notes': 'SecretInternal1241'})
        injury.with_context(mail_notrack=True).write(
            {'external_notes': 'VisibleExternal1241'})
        return injury

    def test_portal_tp_sees_both_scopes(self):
        injury = self._seed_http_fixture()
        self._login_tp()
        resp = self.url_open(f'/my/injury/{injury.id}/notes/history')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('SecretInternal1241', resp.text)
        self.assertIn('VisibleExternal1241', resp.text)

    def test_portal_tp_scope_filter(self):
        injury = self._seed_http_fixture()
        self._login_tp()
        resp = self.url_open(f'/my/injury/{injury.id}/notes/history?scope=internal')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('SecretInternal1241', resp.text)
        self.assertNotIn('VisibleExternal1241', resp.text)
        resp = self.url_open(f'/my/injury/{injury.id}/notes/history?scope=external')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('SecretInternal1241', resp.text)
        self.assertIn('VisibleExternal1241', resp.text)

    def test_portal_coach_sees_external_only(self):
        injury = self._seed_http_fixture()
        self._login_coach()
        resp = self.url_open(f'/my/injury/{injury.id}/notes/history')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('SecretInternal1241', resp.text)
        self.assertIn('VisibleExternal1241', resp.text)

    def test_portal_coach_scope_tampering_denied(self):
        injury = self._seed_http_fixture()
        self._login_coach()
        for tampered in ('internal', 'all', 'bogus'):
            resp = self.url_open(
                f'/my/injury/{injury.id}/notes/history?scope={tampered}')
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn('SecretInternal1241', resp.text,
                             f"scope={tampered} must not leak internal notes")

    def test_portal_unrelated_user_denied(self):
        injury = self._seed_http_fixture()
        self._login_plain()
        resp = self.url_open(f'/my/injury/{injury.id}/notes/history')
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('SecretInternal1241', resp.text)
        self.assertNotIn('VisibleExternal1241', resp.text)

    def test_portal_save_credits_authenticated_author(self):
        """/my/injury/save writes via injury.sudo(); the history row must
        still credit the authenticated portal user, not the superuser."""
        injury = self._new_injury()
        self._login_tp()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(),
            'injury_id': injury.id,
            'diagnosis': injury.diagnosis,
            'internal_notes': 'Portal-authored internal 1241',
            'stage': 'active',
        })
        self.assertEqual(resp.status_code, 200)
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, 'Portal-authored internal 1241')
        self.assertEqual(rows.author_id, self.tp)
