"""Security hotfix 19.0.1.42.4 — who may read sports.treatment.note.

The model had no record rule while base.group_portal (every portal account)
and the portal coach group held a read ACL, so any logged-in portal user could
read every treatment note over /web/dataset/call_kw.

Acceptance criteria:

1. A portal treatment professional staffing team A reads (search / read) the
   notes of team-A patients and NOT those of team-B patients.
2. A portal coach holds no access to treatment notes at all (no coach-facing
   screen shows them): ORM access raises AccessError. The coach's player page
   still renders (200) and the standalone notes page is refused
   (redirect to the player page, task 1577).
3. A plain portal user (portal group only) gets AccessError; a team staffer
   with role « other » and no clinic portal group still opens the player page.
4. Internal clinic user / internal TP / clinic admin keep reading every note
   (unchanged).
5. The portal TP still sees team-A notes on the player page and the notes page.
"""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon

NOTE_A = 'HOTFIX-NOTE-TEAM-A'
NOTE_B = 'HOTFIX-NOTE-TEAM-B'


@tagged('-at_install', 'post_install')
class TestTreatmentNoteAccessHotfix(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Note = env['sports.treatment.note']
        cls.note_a = Note.create({
            'patient_id': cls.player.id, 'note': NOTE_A, 'user_id': cls.tp.id})
        cls.note_b = Note.create({
            'patient_id': cls.player_b.id, 'note': NOTE_B})
        cls.all_notes = cls.note_a | cls.note_b

        def _internal(login, group_xmlid):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [Command.set([
                    env.ref('base.group_user').id, env.ref(group_xmlid).id])],
            })
        cls.int_user = _internal(
            'hotfix.int.user', 'bemade_sports_clinic.group_sports_clinic_user')
        cls.int_tp = _internal(
            'hotfix.int.tp',
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.int_admin = _internal(
            'hotfix.int.admin', 'bemade_sports_clinic.group_sports_clinic_admin')

        # Team staffer with role « other »: portal group only, no clinic group.
        cls.other_staff = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Other Staff', 'login': 'pc.other@example.com',
            'password': 'pc-other',
            'group_ids': [Command.set([env.ref('base.group_portal').id])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.other_staff.partner_id.id,
            'role': 'other',
        })

    def _notes_as(self, user):
        return self.env['sports.treatment.note'].with_user(user)

    # 1. portal TP: team-scoped
    def test_portal_tp_reads_only_staffed_team_notes(self):
        Note = self._notes_as(self.tp)
        found = Note.search([('id', 'in', self.all_notes.ids)])
        self.assertEqual(found, self.note_a)
        self.assertEqual(found.read(['note'])[0]['note'], NOTE_A)
        with mute_logger('odoo.addons.base.models.ir_rule'), \
                self.assertRaises(AccessError):
            Note.browse(self.note_b.id).read(['note'])

    def test_portal_tp_cannot_write_notes_directly(self):
        # Writes go through the sudo portal routes; the ORM stays read-only.
        with mute_logger('odoo.addons.base.models.ir_model'), \
                self.assertRaises(AccessError):
            self._notes_as(self.tp).browse(self.note_a.id).write({'note': 'x'})

    # 2. portal coach: no access
    def test_portal_coach_has_no_access(self):
        Note = self._notes_as(self.coach)
        with mute_logger('odoo.addons.base.models.ir_model'):
            with self.assertRaises(AccessError):
                Note.search([('id', 'in', self.all_notes.ids)])
            with self.assertRaises(AccessError):
                Note.browse(self.note_a.id).read(['note'])

    def test_coach_player_page_renders_without_notes(self):
        self._login_coach()
        resp = self.url_open(
            f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(NOTE_A, resp.text)

    def test_coach_notes_page_refused(self):
        # Mainline (task 1577) sends a non-TP back to the player page.
        self._login_coach()
        resp = self.url_open(f'/my/patient/notes?patient_id={self.player.id}',
                             allow_redirects=False)
        self.assertIn(resp.status_code, (303, 302, 403))
        self.assertNotIn(NOTE_A, resp.text)

    # 3. plain portal / role « other »
    def test_plain_portal_user_has_no_access(self):
        Note = self._notes_as(self.plain)
        with mute_logger('odoo.addons.base.models.ir_model'):
            with self.assertRaises(AccessError):
                Note.search([])
            with self.assertRaises(AccessError):
                Note.browse(self.note_a.id).read(['note'])

    def test_other_role_staffer_player_page_renders(self):
        self.assertFalse(self.other_staff.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional'))
        with mute_logger('odoo.addons.base.models.ir_model'), \
                self.assertRaises(AccessError):
            self._notes_as(self.other_staff).search([])
        self.authenticate('pc.other@example.com', 'pc-other')
        resp = self.url_open(
            f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(NOTE_A, resp.text)

    # 4. internal users unchanged
    def test_internal_users_read_all_notes(self):
        for user in (self.int_user, self.int_tp, self.int_admin):
            with self.subTest(user=user.login):
                found = self._notes_as(user).search([('id', 'in', self.all_notes.ids)])
                self.assertEqual(found, self.all_notes)
                found.read(['note'])

    # 5. portal TP screens still work
    def test_portal_tp_screens_show_team_notes(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(NOTE_A, resp.text)
        resp = self.url_open(f'/my/patient/notes?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(NOTE_A, resp.text)
        resp = self.url_open(f'/my/patient/notes?patient_id={self.player_b.id}')
        self.assertNotEqual(resp.status_code, 200)
        self.assertNotIn(NOTE_B, resp.text)
