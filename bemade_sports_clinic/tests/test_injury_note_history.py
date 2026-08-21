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
- Task 1404 — normalized capture: comparison is strip-normalized, and an
  essentially-empty NEW value logs NOTHING, genuine clears included (customer
  decision, traceability trade-off accepted). Whitespace-only diffs log
  nothing in either direction on either field; re-adding after a clear logs
  the new content; stored content stays raw. The 19.0.1.24.2 migration
  deletes pre-existing essentially-empty rows and nothing else.
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

    # ---- normalized capture (task 1404) ----

    def test_clear_logs_nothing_and_keeps_prior_rows(self):
        """Behaviour row 3: clearing a note logs no row; the field stays
        empty; prior rows are untouched."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'A + B'})
        self.assertEqual(len(self._rows(injury, scope='internal')), 1)

        injury.with_context(mail_notrack=True).write({'internal_notes': False})

        self.assertFalse(injury.internal_notes)
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 1, "a clear must not create a history row")
        self.assertEqual(rows.content, 'A + B',
                         "the prior snapshot must keep its content")

    def test_whitespace_only_diff_logs_nothing(self):
        """Behaviour row 4: whitespace-only diffs log nothing — both
        directions, both fields."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'A'})
        injury.with_context(mail_notrack=True).write({'external_notes': 'B'})
        before = len(self._rows(injury))

        # padding an existing value
        injury.with_context(mail_notrack=True).write({'internal_notes': 'A '})
        injury.with_context(mail_notrack=True).write({'external_notes': '  B'})
        # stripping the padding back off
        injury.with_context(mail_notrack=True).write({'internal_notes': 'A'})
        injury.with_context(mail_notrack=True).write({'external_notes': 'B'})

        self.assertEqual(len(self._rows(injury)), before,
                         "whitespace-only diffs must not create rows")

    def test_empty_to_whitespace_logs_nothing(self):
        """Behaviour row 4 (empty side): '' -> whitespace-only logs nothing,
        on both fields."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': '   '})
        injury.with_context(mail_notrack=True).write({'external_notes': ' '})
        self.assertFalse(self._rows(injury))
        # and back to genuinely empty — still nothing
        injury.with_context(mail_notrack=True).write({'internal_notes': False})
        self.assertFalse(self._rows(injury))

    def test_readd_after_clear_logs_new_content(self):
        """Behaviour row 5: re-adding a note after a clear logs the new
        content — no blank row anywhere."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': 'A'})
        injury.with_context(mail_notrack=True).write({'internal_notes': False})
        injury.with_context(mail_notrack=True).write({'internal_notes': 'C'})

        rows = self._rows(injury, scope='internal')
        self.assertEqual(rows.mapped('content'), ['A', 'C'])
        self.assertFalse(any(not (r.content or '').strip() for r in rows),
                         "no history row may have essentially-empty content")

    def test_logged_content_stays_raw(self):
        """Normalization is for comparison only — the stored snapshot keeps
        the raw (un-stripped) value the user saved."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write({'internal_notes': '  raw kept  '})
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, '  raw kept  ')

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

    def test_create_whitespace_only_notes_seed_nothing(self):
        """Task 1404 (create path): whitespace-only initial notes seed no
        history row on either field."""
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'team_id': self.team_a.id,
            'diagnosis': 'Created with blank notes',
            'internal_notes': '   ',
            'external_notes': ' ',
        })
        self.assertFalse(self._rows(injury))

    def test_create_raw_content_seeded_unstripped(self):
        """Task 1404 (create path): a real initial note is stored raw."""
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'team_id': self.team_a.id,
            'diagnosis': 'Created with padded note',
            'internal_notes': '  padded initial  ',
        })
        rows = self._rows(injury, scope='internal')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, '  padded initial  ')

    # ---- migration 19.0.1.24.2 (task 1404) ----

    def _load_1404_migration(self):
        import importlib.util
        import os
        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(
            module_root, 'migrations', '19.0.1.24.2', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location(
            'bsc_migration_19_0_1_24_2', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_purges_blank_rows_only(self):
        """The 19.0.1.24.2 migration deletes essentially-empty history rows
        (NULL, '', whitespace-only) and nothing else. Blank rows are staged
        with raw SQL — the way prod got them, pre-fix — since the fixed
        capture can no longer produce them."""
        injury = self._new_injury()
        injury.with_context(mail_notrack=True).write(
            {'internal_notes': 'Keep me 1404'})
        keeper = self._rows(injury, scope='internal')
        self.assertEqual(len(keeper), 1)

        for blank in ('', '   ', None):
            self.env.cr.execute(
                """
                INSERT INTO sports_injury_note_history
                       (injury_id, scope, content, author_id, note_datetime)
                VALUES (%s, 'internal', %s, %s, now() at time zone 'UTC')
                """,
                (injury.id, blank, self.env.uid),
            )
        self.env.invalidate_all()
        self.assertEqual(len(self._rows(injury)), 4)

        migration = self._load_1404_migration()
        migration.migrate(self.env.cr, '19.0.1.24.1')
        self.env.invalidate_all()

        rows = self._rows(injury)
        self.assertEqual(len(rows), 1,
                         "only the blank rows may be deleted")
        self.assertEqual(rows.content, 'Keep me 1404')

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

    def test_history_page_breadcrumbs(self):
        """Candidate human-test finding (2026-07-10): the history page must
        carry a breadcrumb trail back to where it was reached from — team-aware
        when a team context is passed, player-centric otherwise."""
        injury = self._seed_http_fixture()
        self._login_tp()
        url = f'/my/injury/{injury.id}/notes/history'

        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('breadcrumb', resp.text)
        self.assertIn('Edit Injury', resp.text)
        self.assertIn('/my/players', resp.text)

        team = injury.patient_id.team_ids[:1]
        if team:
            resp = self.url_open(f'{url}?team_id={team.id}')
            self.assertEqual(resp.status_code, 200)
            self.assertIn('/my/teams', resp.text)
            self.assertIn(f'team_id={team.id}', resp.text)
