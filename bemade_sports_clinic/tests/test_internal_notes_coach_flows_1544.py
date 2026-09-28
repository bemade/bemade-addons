"""Task 1544 — coach flows keep working once internal notes are restricted (AC2).

Use case: ``sports.patient.injury.internal_notes`` now carries field groups
(staff + portal treatment professionals). Every page, fragment, email and cron
a coach touches must behave as before on a team whose injuries HAVE internal
notes — no AccessError, no 500 — and still never show the note to the coach.

Acceptance criteria:
- As a coach, with an active injury that has internal notes: the team page
  (legacy and app shell), the players list, the player page, the recent-
  changes fragment and the frozen digest page answer 200 and do not contain
  the internal note.
- The digest capture (cron), the urgent-notification cron and the daily
  briefing cron run without error on that team; the coach's view of the
  captured digest has no internal note.
- A coach can still report an injury and edit an injury's external fields
  through the portal; a coach posting ``internal_notes`` is ignored.
- A TP still sees the internal note on the team page player card.

All fixtures are synthetic.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon

SECRET = 'ZZ-1544-coach-flow-secret'
SWITCH = 'bemade_sports_clinic.app_shell_enabled'


@tagged('-at_install', 'post_install')
class TestInternalNotesCoachFlows1544(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.write({'internal_notes': SECRET, 'external_notes': 'ZZ ext visible'})
        cls.env.flush_all()
        cls.env.cr.precommit.run()

    def _get_ok(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertNotIn(SECRET, resp.text, url)
        return resp

    # -- Pages ---------------------------------------------------------------

    def test_coach_pages_legacy(self):
        self._login_coach()
        self._get_ok('/my/team/%s' % self.team_a.id)
        self._get_ok('/my/team?team_id=%s' % self.team_a.id)
        self._get_ok('/my/teams')
        self._get_ok('/my/players')
        resp = self._get_ok('/my/player?player_id=%s' % self.player.id)
        self.assertIn('ZZ ext visible', resp.text)
        self._get_ok('/my/player/%s/recent-changes' % self.player.id)
        self._get_ok('/my/injury/edit?injury_id=%s' % self.injury.id)

    def test_coach_pages_app_shell(self):
        self.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True')
        self._login_coach()
        self._get_ok('/my/home')
        self._get_ok('/my/team/%s' % self.team_a.id)
        self._get_ok('/my/players')
        self._get_ok('/my/player?player_id=%s' % self.player.id)

    def test_tp_still_sees_internal_note_on_card(self):
        self._login_tp()
        resp = self.url_open('/my/team/%s' % self.team_a.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(SECRET, resp.text, 'the TP card keeps the internal note')

    def test_card_detail_for_coach_env(self):
        """The live card's injury dict built in the coach's env: no error, no
        internal note; in a TP env it keeps it."""
        coach_player = self.player.with_user(self.coach)
        details = coach_player._card_active_injuries(is_treatment_prof=False)
        self.assertTrue(details)
        self.assertEqual({d['internal_notes'] for d in details}, {''})
        detail = coach_player._card_injury_detail(self.injury.with_user(self.coach))
        self.assertEqual(detail['internal_notes'], '')
        tp_detail = self.player.with_user(self.tp)._card_injury_detail(
            self.injury.with_user(self.tp))
        self.assertEqual(tp_detail['internal_notes'], SECRET)

    # -- Crons / digest -------------------------------------------------------

    def test_digest_capture_and_coach_view(self):
        Digest = self.env['sports.team.digest']
        Digest._cron_capture_team_digests()
        digest = Digest._capture_team(
            self.team_a, fields.Datetime.now(), fields.Date.today(), 'UTC')
        self.assertTrue(digest)
        coach_players = digest.with_user(self.coach)._render_for_role('coach')
        self.assertNotIn(SECRET, repr(coach_players))
        tp_players = digest._render_for_role('tp')
        self.assertIn(SECRET, repr(tp_players), 'TP snapshot keeps the superset')
        self._login_coach()
        self._get_ok('/my/team/%s/digest/%s' % (self.team_a.id, digest.id))
        self._get_ok('/my/team/%s/digest-history' % self.team_a.id)

    def test_urgent_and_briefing_crons_run(self):
        self.env['sports.patient']._cron_send_urgent_notifications(
            now=fields.Datetime.now() + timedelta(hours=1))
        self.env['res.users']._cron_send_morning_digests(
            now=fields.Datetime.now() + timedelta(hours=12))
        mails = self.env['mail.mail'].sudo().search([
            ('create_date', '>=', fields.Datetime.now() - timedelta(minutes=5))])
        for mail in mails:
            self.assertNotIn(SECRET, mail.body_html or '')

    # -- Injury create / edit by a coach ------------------------------------

    def test_coach_creates_injury(self):
        self._login_coach()
        before = self.env['sports.patient.injury'].search_count(
            [('patient_id', '=', self.player.id)])
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'ZZ coach report', 'external_notes': 'ZZ coach ext',
            'internal_notes': 'ZZ coach sneaky', 'injury_date': '2026-09-01',
        })
        self.assertEqual(resp.status_code, 200)
        created = self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', 'ZZ coach report')])
        self.assertEqual(len(created), 1, 'coach injury report still works')
        self.assertEqual(
            self.env['sports.patient.injury'].search_count(
                [('patient_id', '=', self.player.id)]), before + 1)
        self.assertFalse(created.internal_notes, 'a coach cannot set internal notes')

    def test_coach_edits_injury(self):
        self._login_coach()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id,
            'diagnosis': 'Sprain', 'external_notes': 'ZZ coach ext edit',
            'internal_notes': 'ZZ coach sneaky',
        })
        self.assertEqual(resp.status_code, 200)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'ZZ coach ext edit')
        self.assertEqual(self.injury.internal_notes, SECRET, 'internal notes untouched')

    def test_coach_partial_save(self):
        self._login_coach()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'ZZ partial ext', 'internal_notes': 'ZZ coach sneaky',
        })
        self.assertIn(resp.status_code, (200, 204))
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'ZZ partial ext')
        self.assertEqual(self.injury.internal_notes, SECRET)
