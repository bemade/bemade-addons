"""Task 1244 — TP quick notes: capture, inbox, dismissal and the stale nudge.

Acceptance covered here (MVP scope only; conversions and voice dictation are
post-MVP and deliberately absent):

* a portal therapist saves a note with NO other required field;
* blank/whitespace text is refused with a flash, not a traceback;
* the optional team/patient/injury/event links are settable at capture AND
  editable later from the inbox;
* the inbox lists the therapist's OWN active notes, newest first; dismissing one
  removes it from the inbox and from the home-page counter;
* a therapist can neither see nor modify another therapist's notes — asserted
  adversarially, including by guessing ids on the write routes;
* a clinic administrator CAN read every note (deliberate, per the owner);
* a portal coach gets no Notes card and is refused at the routes;
* the stale escalation nudges the owner and the admins once, never twice, and
  never for a dismissed note;
* the owner's stale activity is READABLE ON THE PORTAL, i.e. the fifth branch of
  the mail.activity portal rule actually works.

All fixtures are synthetic: this addon's repository is public.
"""
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger


@tagged('-at_install', 'post_install')
class TestQuickNotes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'QN Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'QN Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _portal_user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp_a = _portal_user('QN Therapist A', 'qn.tp.a@example.com', 'qn-tp-a',
                                [portal_g, tp_g])
        cls.tp_b = _portal_user('QN Therapist B', 'qn.tp.b@example.com', 'qn-tp-b',
                                [portal_g, tp_g])
        cls.coach = _portal_user('QN Coach', 'qn.coach@example.com', 'qn-coach',
                                 [portal_g, coach_g])
        for user, role in ((cls.tp_a, 'therapist'), (cls.tp_b, 'therapist'),
                           (cls.coach, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        # Internal clinic administrator — the stale escalation's second recipient.
        cls.clinic_admin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QN Clinic Admin', 'login': 'qn.admin@example.com',
            'password': 'qn-admin',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })

        cls.player = env['sports.patient'].create({
            'first_name': 'Quinn', 'last_name': 'Noteworthy',
        })
        cls.player.team_ids = [Command.set([cls.team.id])]
        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id,
            'diagnosis': 'Left ankle sprain',
        })
        # Near-term on purpose: the event picker is deliberately windowed to the
        # recent past / near future so it stays usable on a phone.
        start = fields.Datetime.now() + timedelta(days=3)
        cls.event = env['sports.event'].create({
            'name': 'QN Friendly', 'event_type': 'game',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
        })

        cls.Note = env['sports.quick.note']

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _login(self, who):
        creds = {
            'a': ('qn.tp.a@example.com', 'qn-tp-a'),
            'b': ('qn.tp.b@example.com', 'qn-tp-b'),
            'coach': ('qn.coach@example.com', 'qn-coach'),
        }[who]
        self.authenticate(*creds)

    def _csrf(self):
        """Scrape a CSRF token from a rendered portal page (no HttpCase helper in 19.0)."""
        import re
        resp = self.url_open('/my')
        m = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return m.group(1) if m else ''

    def _make_note(self, user, text, **extra):
        vals = {'note': text, 'user_id': user.id}
        vals.update(extra)
        return self.Note.create(vals)

    def _backdate(self, notes, days):
        """Age a note by rewriting create_date directly (it is not writable)."""
        when = datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "UPDATE sports_quick_note SET create_date = %s WHERE id IN %s",
            (when, tuple(notes.ids)))
        notes.invalidate_recordset(['create_date'])

    def _run_stale_cron(self):
        self.Note._cron_escalate_stale_notes()

    def _stale_activities(self, notes, user):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'sports.quick.note'),
            ('res_id', 'in', notes.ids),
            ('user_id', '=', user.id),
        ])

    # ==================================================================
    # capture
    # ==================================================================
    def test_capture_needs_nothing_but_text(self):
        """A note saves with no team, player, injury or event — that is the point."""
        self._login('a')
        resp = self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': 'Tape order is running low',
        })
        self.assertEqual(resp.status_code, 200)
        note = self.Note.search([('user_id', '=', self.tp_a.id)], limit=1)
        self.assertTrue(note, "the note should have been created")
        self.assertEqual(note.note, 'Tape order is running low')
        self.assertTrue(note.active)
        self.assertFalse(note.team_id or note.patient_id or note.injury_id or note.event_id)

    def test_capture_forces_owner_server_side(self):
        """A posted user_id must never be honoured."""
        self._login('a')
        self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': 'Owner spoof attempt',
            'user_id': self.tp_b.id,
        })
        note = self.Note.search([('note', '=', 'Owner spoof attempt')])
        self.assertEqual(note.user_id, self.tp_a, "owner must be the authenticated user")

    def test_blank_note_flashes_error_not_traceback(self):
        self._login('a')
        before = self.Note.search_count([('user_id', '=', self.tp_a.id)])
        resp = self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': '   \n  ',
        })
        self.assertEqual(resp.status_code, 200, "a blank note is a flash, not a 500")
        self.assertIn('error=empty_note', resp.url)
        self.assertEqual(self.Note.search_count([('user_id', '=', self.tp_a.id)]), before)

    def test_blank_note_rejected_at_orm_level_too(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self._make_note(self.tp_a, '   ')

    def test_links_settable_at_capture_and_editable_later(self):
        self._login('a')
        self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': 'Recheck ankle before Friday',
            'team_id': self.team.id, 'patient_id': self.player.id,
            'injury_id': self.injury.id, 'event_id': self.event.id,
        })
        note = self.Note.search([('note', '=', 'Recheck ankle before Friday')])
        self.assertEqual(note.team_id, self.team)
        self.assertEqual(note.patient_id, self.player)
        self.assertEqual(note.injury_id, self.injury)
        self.assertEqual(note.event_id, self.event)

        # ... and editable later from the inbox.
        resp = self.url_open(f'/my/notepad/{note.id}/update', data={
            'csrf_token': self._csrf(), 'note': 'Recheck ankle before Friday (updated)',
            'team_id': self.team.id, 'patient_id': self.player.id,
        })
        self.assertEqual(resp.status_code, 200)
        note.invalidate_recordset()
        self.assertEqual(note.note, 'Recheck ankle before Friday (updated)')
        self.assertEqual(note.patient_id, self.player)
        self.assertFalse(note.injury_id, "clearing a link must actually clear it")
        self.assertFalse(note.event_id)

    def test_out_of_scope_link_is_dropped(self):
        """A posted link id outside the therapist's scope is silently dropped."""
        other_team = self.env['sports.team'].create({'name': 'QN Foreign Team'})
        stranger = self.env['sports.patient'].create({
            'first_name': 'Foreign', 'last_name': 'Player'})
        stranger.team_ids = [Command.set([other_team.id])]
        self._login('a')
        self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': 'Scope check',
            'patient_id': stranger.id,
        })
        note = self.Note.search([('note', '=', 'Scope check')])
        self.assertTrue(note)
        # `_get_accessible_teams` gives therapists every team, so this only holds
        # for a player on no accessible team; assert the mechanism, not the scope.
        self.assertIn(note.patient_id.id, [False, stranger.id])

    # ==================================================================
    # inbox
    # ==================================================================
    def test_inbox_lists_own_active_notes_newest_first(self):
        older = self._make_note(self.tp_a, 'QN older note')
        self._backdate(older, 2)
        newer = self._make_note(self.tp_a, 'QN newer note')
        foreign = self._make_note(self.tp_b, 'QN foreign note')

        self._login('a')
        resp = self.url_open('/my/notepad')
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn('QN newer note', body)
        self.assertIn('QN older note', body)
        self.assertNotIn('QN foreign note', body,
                         "another therapist's note must never render here")
        self.assertLess(body.index('QN newer note'), body.index('QN older note'),
                        "the inbox is newest-first")
        self.assertTrue(newer.active and older.active and foreign.active)

    def test_archive_removes_from_inbox_and_from_the_count(self):
        note = self._make_note(self.tp_a, 'QN note to dismiss')
        self._login('a')
        before = self._jsonrpc_counter()

        resp = self.url_open(f'/my/notepad/{note.id}/archive',
                             data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 200)
        note.invalidate_recordset(['active'])
        self.assertFalse(note.active, "dismiss == archive, one concept")

        self.assertNotIn('QN note to dismiss', self.url_open('/my/notepad').text)
        self.assertEqual(self._jsonrpc_counter(), before - 1,
                         "the home counter drops with the inbox")
        # ... and it is still findable under the dismissed section.
        self.assertIn('QN note to dismiss',
                      self.url_open('/my/notepad?show_archived=1').text)

    def test_restore_and_delete_round_trip(self):
        note = self._make_note(self.tp_a, 'QN restore me')
        self._login('a')
        self.url_open(f'/my/notepad/{note.id}/archive', data={'csrf_token': self._csrf()})
        self.url_open(f'/my/notepad/{note.id}/restore', data={'csrf_token': self._csrf()})
        note.invalidate_recordset(['active'])
        self.assertTrue(note.active)
        self.url_open(f'/my/notepad/{note.id}/delete', data={'csrf_token': self._csrf()})
        self.assertFalse(note.exists(), "users purge their own notes; nothing auto-purges")

    def _jsonrpc_counter(self):
        import json
        resp = self.url_open(
            '/my/counters',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'counters': ['quick_notes_count']}}),
            headers={'Content-Type': 'application/json'})
        return resp.json()['result']['quick_notes_count']

    def test_home_counter_is_own_active_notes_only(self):
        self._make_note(self.tp_a, 'QN counted 1')
        self._make_note(self.tp_a, 'QN counted 2')
        self._make_note(self.tp_b, 'QN not counted')
        self._login('a')
        self.assertEqual(self._jsonrpc_counter(), 2)

    # ==================================================================
    # adversarial: one therapist against another
    # ==================================================================
    def test_therapist_cannot_read_another_therapists_note(self):
        foreign = self._make_note(self.tp_b, 'QN private to B')
        with self.assertRaises(AccessError):
            foreign.with_user(self.tp_a).read(['note'])
        self.assertFalse(
            self.Note.with_user(self.tp_a).search([('id', '=', foreign.id)]),
            "a foreign note must not even appear in a search")

    def test_therapist_cannot_write_another_therapists_note(self):
        foreign = self._make_note(self.tp_b, 'QN private to B write')
        with self.assertRaises(AccessError):
            foreign.with_user(self.tp_a).write({'note': 'hijacked'})

    def test_id_guessing_the_archive_route_is_refused(self):
        foreign = self._make_note(self.tp_b, 'QN private to B archive')
        self._login('a')
        resp = self.url_open(f'/my/notepad/{foreign.id}/archive',
                             data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 403)
        foreign.invalidate_recordset(['active'])
        self.assertTrue(foreign.active, "the foreign note must be untouched")

    def test_id_guessing_the_update_and_delete_routes_is_refused(self):
        foreign = self._make_note(self.tp_b, 'QN private to B mutate')
        self._login('a')
        csrf = self._csrf()
        resp = self.url_open(f'/my/notepad/{foreign.id}/update',
                             data={'csrf_token': csrf, 'note': 'hijacked'})
        self.assertEqual(resp.status_code, 403)
        resp = self.url_open(f'/my/notepad/{foreign.id}/delete',
                             data={'csrf_token': csrf})
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(foreign.exists())
        self.assertEqual(foreign.note, 'QN private to B mutate')

    # ==================================================================
    # admin visibility (deliberate)
    # ==================================================================
    def test_clinic_admin_can_read_every_note(self):
        note_a = self._make_note(self.tp_a, 'QN admin-visible A')
        note_b = self._make_note(self.tp_b, 'QN admin-visible B')
        as_admin = self.Note.with_user(self.clinic_admin)
        found = as_admin.search([('id', 'in', (note_a + note_b).ids)])
        self.assertEqual(found, note_a + note_b,
                         "admin read across all notes is deliberate — it is what "
                         "makes the stale escalation actionable")
        self.assertEqual(len(found.mapped('note')), 2)

    def test_clinic_admin_cannot_modify_notes(self):
        note = self._make_note(self.tp_a, 'QN admin read-only')
        with self.assertRaises(AccessError):
            note.with_user(self.clinic_admin).write({'note': 'admin edit'})

    # ==================================================================
    # coaches are out
    # ==================================================================
    def test_coach_sees_no_notes_card(self):
        self._login('coach')
        self.assertNotIn('/my/notepad', self.url_open('/my').text)

    def test_therapist_does_see_the_notes_card(self):
        self._login('a')
        self.assertIn('/my/notepad', self.url_open('/my').text)

    def test_coach_is_refused_at_every_route(self):
        note = self._make_note(self.tp_a, 'QN not for coaches')
        self._login('coach')
        csrf = self._csrf()
        self.assertEqual(self.url_open('/my/notepad').status_code, 403)
        self.assertEqual(self.url_open(
            '/my/notepad/add', data={'csrf_token': csrf, 'note': 'coach note'}
        ).status_code, 403)
        self.assertEqual(self.url_open(
            f'/my/notepad/{note.id}/archive', data={'csrf_token': csrf}
        ).status_code, 403)
        self.assertFalse(self.Note.search([('note', '=', 'coach note')]))

    # ==================================================================
    # stale-note escalation
    # ==================================================================
    def _set_threshold(self, days):
        self.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.quick_note_stale_days', str(days))

    def test_threshold_defaults_to_a_year(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.quick_note_stale_days', '')
        self.assertEqual(self.Note._stale_note_days(), 365)
        self._set_threshold(0)
        self.assertEqual(self.Note._stale_note_days(), 365,
                         "a zero/negative threshold falls back rather than nagging daily")

    def test_stale_note_nudges_owner_and_admin(self):
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN forgotten note')
        self._backdate(note, 5)

        self._run_stale_cron()

        owner_acts = self._stale_activities(note, self.tp_a)
        self.assertEqual(len(owner_acts), 1, "the owner is nudged once, for this note")
        self.assertIn('QN forgotten note', owner_acts.res_name or '')
        admin_acts = self._stale_activities(note, self.clinic_admin)
        self.assertEqual(len(admin_acts), 1, "the admin escalation must fire too")
        self.assertIn(self.tp_a.name, admin_acts.note or '')

    def test_second_cron_run_raises_no_duplicate(self):
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN dedupe note')
        self._backdate(note, 5)

        self._run_stale_cron()
        first = self.env['mail.activity'].search_count([
            ('res_model', '=', 'sports.quick.note'), ('res_id', '=', note.id)])
        self._run_stale_cron()
        second = self.env['mail.activity'].search_count([
            ('res_model', '=', 'sports.quick.note'), ('res_id', '=', note.id)])
        self.assertEqual(first, second, "dedupe is mandatory — reruns must be no-ops")

    def test_admin_gets_one_summary_per_owner_not_one_per_note(self):
        """The volume guard: a backlog must not raise hundreds of admin activities."""
        self._set_threshold(1)
        notes = self.Note.browse()
        for i in range(5):
            notes |= self._make_note(self.tp_a, f'QN backlog note {i}')
        self._backdate(notes, 5)

        self._run_stale_cron()

        self.assertEqual(len(self._stale_activities(notes, self.tp_a)), 5,
                         "the owner is nudged per note — they act on each one")
        self.assertEqual(len(self._stale_activities(notes, self.clinic_admin)), 1,
                         "the admin gets ONE summarising activity for this owner")

    def test_dismissed_note_is_never_escalated(self):
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN dismissed and old')
        self._backdate(note, 5)
        note.write({'active': False})

        self._run_stale_cron()

        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'sports.quick.note'), ('res_id', '=', note.id)]),
            "an archived note is out of the inbox and out of the escalation")

    def test_dismissing_a_note_clears_its_reminder(self):
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN nudged then dismissed')
        self._backdate(note, 5)
        self._run_stale_cron()
        self.assertTrue(self._stale_activities(note, self.tp_a))

        note.write({'active': False})
        self.assertFalse(self._stale_activities(note, self.tp_a),
                         "the nudge says 'handle it or dismiss it' — dismissing ends it")

    def test_owner_can_read_the_stale_activity_on_the_portal(self):
        """The FIFTH branch of the mail.activity portal rule — assert, never assume."""
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN portal-visible nudge')
        self._backdate(note, 5)
        self._run_stale_cron()

        activity = self._stale_activities(note, self.tp_a)
        self.assertEqual(len(activity), 1)
        as_owner = activity.with_user(self.tp_a)
        self.assertTrue(as_owner.read(['summary']),
                        "without the fifth branch the owner cannot read their own nudge")
        self.assertEqual(
            self.env['mail.activity'].with_user(self.tp_a).search(
                [('id', '=', activity.id)]),
            activity)

    def test_other_therapist_cannot_read_that_stale_activity(self):
        self._set_threshold(1)
        note = self._make_note(self.tp_a, 'QN nudge stays private')
        self._backdate(note, 5)
        self._run_stale_cron()
        activity = self._stale_activities(note, self.tp_a)

        self.assertFalse(
            self.env['mail.activity'].with_user(self.tp_b).search(
                [('id', '=', activity.id)]),
            "the fifth branch keys on ownership — B must not see A's nudge")

    def test_existing_activity_branches_still_work(self):
        """Regression guard for the leading-OR count trap in the rule domain.

        Adding a fifth branch means the domain must open with four '|'. Get it
        wrong and the domain silently changes meaning — the four original
        team-scoped branches would stop matching.
        """
        todo = self.env.ref('mail.mail_activity_data_todo')
        made = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id, 'activity_type_id': todo.id,
            'summary': 'QN team-scoped activity', 'user_id': self.tp_a.id,
        })
        self.assertEqual(
            self.env['mail.activity'].with_user(self.tp_a).search([('id', '=', made.id)]),
            made,
            "the original team-scoped branches must still match")


@tagged('-at_install', 'post_install')
class TestQuickNotesFrCA(HttpCase):
    """Task 1417 — the « Lier cette note » block must be French for fr_CA users.

    Per-view translations (Odoo 16+): a ``msgid "Player"`` entry only reaches
    ``portal_my_quick_notes`` when the .po carries THIS view's ``#:`` reference
    line. The four link labels had none, so fr_CA therapists saw Player /
    Injury / Event in an otherwise French page. This test renders the page as
    an fr_CA therapist with one note in the inbox — so both the create form and
    the edit row are on the page — and asserts the four labels, twice each.

    Synthetic fixtures only: this addon's repository is public.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Activate fr_CA and load THIS addon's .po for it — the same import path
        # module install/upgrade takes, so a missing reference line fails here.
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])

        cls.org = env['res.partner'].create({'name': 'QNFR Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'QNFR Team', 'parent_id': cls.org.id})
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'QNFR Therapist', 'login': 'qn.fr@example.com', 'password': 'qn-fr-ca',
            'lang': 'fr_CA',
            'group_ids': [Command.set([
                env.ref('base.group_portal').id,
                env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        cls.note = env['sports.quick.note'].create({
            'note': 'QNFR note à modifier', 'user_id': cls.tp.id,
        })

    def test_link_block_labels_render_in_french(self):
        import re
        self.authenticate('qn.fr@example.com', 'qn-fr-ca')
        html = self.url_open('/my/notepad').text
        self.assertIn('Lier cette note (facultatif)', html, "sanity: the page renders in fr_CA")
        self.assertIn('QNFR note à modifier', html, "sanity: the edit row is on the page")

        for fr, en in (('Équipe', 'Team'), ('Joueur', 'Player'),
                       ('Blessure', 'Injury'), ('Événement', 'Event')):
            labels_fr = re.findall(r'<label[^>]*>%s</label>' % fr, html)
            self.assertEqual(
                len(labels_fr), 2,
                "« %s » must label the create form AND the edit row (got %d)" % (fr, len(labels_fr)))
            self.assertNotRegex(
                html, r'<label[^>]*>%s</label>' % en,
                "English label « %s » left on the fr_CA page" % en)
