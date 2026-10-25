"""Task 1628 — a daily cron raises ONE To-Do when a recently created player
file is still incomplete 48 h after its creation. Synthetic fixtures only
(this repository is public).

Use case: a coach or a therapist adds a player in a hurry (name only). Two
days later the file is still missing the date of birth, an emergency contact
with a phone number or, for a player aged 14 or more, the player's own email
and phone. The person who can complete it gets a To-Do on the player that
lists exactly what is missing; the list follows the file and the To-Do
closes itself once the file is complete.

Acceptance criteria:

* AC-1 Checklist: missing date of birth; no emergency contact (any
  ``contact_ids`` row) with a ``mobile``; for a player aged 14+ — or whose
  date of birth is missing — the player's own email and phone, each listed
  separately. Under 14, the personal email / phone are not asked for.
  Task 1630: a « Not specified » allergy level and medical-alert level, each
  listed (« Niveau d'allergies » / « Alerte médicale »).
* AC-2 Scope: only players created at or after the cut-off parameter
  ``bemade_sports_clinic.incomplete_todo_since`` (set by the 19.0.1.94.0
  post-migrate to the upgrade time) AND more than 48 h ago. Archived players
  are ignored. No cut-off parameter → the cron sets it to now and raises
  nothing.
* AC-3 One To-Do per player (technical flag ``patient_incomplete_todo`` on
  ``mail.activity``): a second run creates nothing new; a filled item drops
  off the list on the next run; a complete file closes the To-Do (marked
  done); a To-Do marked done or cancelled by hand while items are still
  missing is never recreated.
* AC-4 Assignee: the creator when they hold treatment-professional rights
  and can see the player (clinic admin, or staff on one of the player's
  teams); otherwise (coach, inactive, no TP rights, not on the team) the
  team's head therapist / therapist (first team, head therapist first);
  otherwise the first clinic admin. Players created by the system / root
  user (script imports) get nothing.
* AC-5 The summary and the list are rendered in the ASSIGNEE's language
  (« Compléter la fiche du joueur » for an fr_CA assignee).
* AC-6 The To-Do shows in the assignee therapist's « My Activities »
  (/my/activities, team scope).
"""
import html
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

CUTOFF_PARAM = 'bemade_sports_clinic.incomplete_todo_since'


class IncompleteTodoCommon(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)

        portal = env.ref('base.group_portal').id
        internal = env.ref('base.group_user').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id

        Users = env['res.users'].with_context(no_reset_password=True)

        def _user(login, groups, lang='en_US'):
            return Users.create({
                'name': login, 'login': f'{login}@example.com', 'password': login,
                'lang': lang, 'group_ids': [Command.set(groups)],
            })

        cls.org = env['res.partner'].create({'name': 'IT Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'IT Team A', 'parent_id': cls.org.id})
        cls.team_nostaff = env['sports.team'].create(
            {'name': 'IT Team B', 'parent_id': cls.org.id})

        cls.coach = _user('it.coach', [portal, coach_g])
        cls.tp_creator = _user('it.tpcreator', [portal, tp_g])
        cls.therapist = _user('it.therapist', [portal, tp_g])
        cls.head_therapist = _user('it.headtherapist', [portal, tp_g])
        cls.outsider_tp = _user('it.outsidertp', [portal, tp_g])
        cls.Staff = env['sports.team.staff']
        for user, role in ((cls.coach, 'coach'), (cls.tp_creator, 'therapist'),
                           (cls.therapist, 'therapist'),
                           (cls.head_therapist, 'head_therapist')):
            cls.Staff.create({'team_id': cls.team.id,
                              'partner_id': user.partner_id.id, 'role': role})
        cls.Staff.create({'team_id': cls.team_nostaff.id,
                          'partner_id': cls.coach.partner_id.id, 'role': 'coach'})

        # The first clinic admin by id is the fallback assignee; make sure a
        # known one exists and is the first (others from the DB are removed
        # from the group for the duration of the test transaction).
        admin_group = env.ref('bemade_sports_clinic.group_sports_clinic_admin')
        cls.clinic_admin = _user('it.clinicadmin', [internal, admin_g])
        others = admin_group.all_user_ids.filtered(
            lambda u: u != cls.clinic_admin and u.id != 1)
        for other in others:
            other.group_ids = [Command.unlink(admin_group.id)]

        env['ir.config_parameter'].sudo().set_param(
            CUTOFF_PARAM, fields.Datetime.to_string(
                fields.Datetime.now() - timedelta(days=30)))
        cls.Activity = env['mail.activity'].sudo()

    # -- helpers ------------------------------------------------------------
    def _player(self, *, creator=None, hours_old=72, teams=None, dob=None,
                email=False, phone=False, contact_mobile=None, name='Kid',
                allergy_level='none', medical_alert_level='none'):
        # Task 1630: both levels are checklist items too; set by default so
        # the other cases keep testing what they test (« Not specified »
        # cases: test_checklist_medical_levels).
        player = self.env['sports.patient'].create({
            'first_name': name, 'last_name': 'Synthetic',
            'team_ids': [Command.set((teams if teams is not None else self.team).ids)],
            'date_of_birth': dob, 'email': email, 'phone': phone,
            # Task 1677: the levels follow the lists — « none » = « none
            # known » ticked, False = nothing on file.
            'allergy_none_confirmed': allergy_level == 'none',
            'medical_none_confirmed': medical_alert_level == 'none',
        })
        if contact_mobile is not None:
            self.env['sports.patient.contact'].create({
                'patient_id': player.id, 'name': 'Parent', 'contact_type': 'mother',
                'mobile': contact_mobile,
            })
        creator = creator or self.tp_creator
        self.env.cr.execute(
            "UPDATE sports_patient SET create_date = %s, create_uid = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=hours_old), creator.id, player.id))
        player.invalidate_recordset(['create_date', 'create_uid'])
        return player

    def _dob(self, years):
        return date.today() - relativedelta(years=years, days=10)

    def _todos(self, player, active=True):
        return self.Activity.with_context(active_test=False).search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', player.id),
            ('patient_incomplete_todo', '=', True), ('active', '=', active),
        ])

    def _text(self, todo):
        return html.unescape(str(todo.note or ''))

    def _run(self):
        self.env['sports.patient']._cron_incomplete_player_todos()


@tagged('post_install', '-at_install')
class TestIncompletePlayerTodo1628(IncompleteTodoCommon):

    # -- AC-1 checklist -----------------------------------------------------
    def test_checklist_missing_dob_asks_for_everything(self):
        player = self._player()
        self.assertEqual(player._sc_incomplete_items(),
                         ['date_of_birth', 'emergency_contact', 'email', 'phone'])

    def test_checklist_14_plus_needs_own_email_and_phone(self):
        player = self._player(dob=self._dob(14), email='kid@example.com',
                              contact_mobile='+1 514 555 0100')
        self.assertEqual(player._sc_incomplete_items(), ['phone'])
        player.phone = '+1 514 555 0101'
        self.assertEqual(player._sc_incomplete_items(), [])

    def test_checklist_under_14_skips_personal_contact(self):
        player = self._player(dob=self._dob(13))
        self.assertEqual(player._sc_incomplete_items(), ['emergency_contact'])

    def test_checklist_medical_levels(self):
        """Task 1630: a « Not specified » allergy / medical-alert level is
        listed; « None » counts as answered."""
        player = self._player(dob=self._dob(10), contact_mobile='+1 514 555 0110',
                              allergy_level=False, medical_alert_level=False)
        self.assertEqual(player._sc_incomplete_items(), ['allergy_level', 'medical_alert_level'])
        self.env['sports.patient.critical.item'].create({
            'patient_id': player.id, 'family': 'allergy', 'name': 'Synthetic peanut', 'life_threatening': True})
        self.assertEqual(player._sc_incomplete_items(), ['medical_alert_level'])
        player.medical_none_confirmed = True
        self.assertEqual(player._sc_incomplete_items(), [])

    def test_medical_levels_in_french_todo(self):
        """Task 1630 / 1677: « Allergies » / « Alerte médicale » in the
        To-Do of an fr_CA assignee."""
        self.tp_creator.lang = 'fr_CA'
        player = self._player(dob=self._dob(10), contact_mobile='+1 514 555 0111',
                              allergy_level=False, medical_alert_level=False)
        self._run()
        text = self._text(self._todos(player))
        self.assertIn('Allergies', text)
        self.assertIn('Alerte médicale', text)

    def test_checklist_contact_without_mobile_does_not_count(self):
        player = self._player(dob=self._dob(10), contact_mobile=False)
        self.assertEqual(player._sc_incomplete_items(), ['emergency_contact'])
        player.contact_ids.mobile = '+1 514 555 0102'
        self.assertEqual(player._sc_incomplete_items(), [])

    # -- AC-2 scope ----------------------------------------------------------
    def test_grace_period_48h(self):
        young = self._player(hours_old=24)
        old = self._player(hours_old=49)
        self._run()
        self.assertFalse(self._todos(young))
        self.assertEqual(len(self._todos(old)), 1)

    def test_cutoff_excludes_older_players(self):
        before = self._player(hours_old=24 * 40)
        self._run()
        self.assertFalse(self._todos(before))

    def test_archived_player_ignored(self):
        player = self._player()
        player.active = False
        self._run()
        self.assertFalse(self._todos(player))

    def test_missing_cutoff_is_initialised_and_nothing_raised(self):
        player = self._player()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(CUTOFF_PARAM, False)
        self._run()
        self.assertFalse(self._todos(player))
        since = fields.Datetime.to_datetime(ICP.get_param(CUTOFF_PARAM))
        self.assertTrue(since)
        self.assertGreater(since, fields.Datetime.now() - timedelta(minutes=5))

    def test_complete_player_gets_nothing(self):
        player = self._player(dob=self._dob(10), contact_mobile='+1 514 555 0103')
        self._run()
        self.assertFalse(self._todos(player))

    # -- AC-3 lifecycle --------------------------------------------------------
    def test_one_todo_updated_then_auto_done(self):
        player = self._player()
        self._run()
        todo = self._todos(player)
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo.activity_type_id, self.env.ref('mail.mail_activity_data_todo'))
        self.assertEqual(todo.date_deadline, fields.Date.context_today(todo))
        self.assertIn('Date of birth', self._text(todo))
        self.assertIn("Player's email", self._text(todo))

        self._run()
        self.assertEqual(todo, self._todos(player), "one To-Do across runs")

        player.date_of_birth = self._dob(12)
        self._run()
        self.assertEqual(todo, self._todos(player))
        self.assertNotIn('Date of birth', self._text(todo))
        self.assertNotIn("Player's email", self._text(todo))
        self.assertNotIn("Player's phone", self._text(todo))
        self.assertIn('Emergency contact with a phone number', self._text(todo))

        self.env['sports.patient.contact'].create({
            'patient_id': player.id, 'name': 'Parent', 'contact_type': 'father',
            'mobile': '+1 514 555 0104',
        })
        self._run()
        self.assertFalse(self._todos(player), "complete file: To-Do closed")
        self.assertEqual(self._todos(player, active=False), todo, "marked done, not deleted")

    def test_manual_done_not_recreated(self):
        player = self._player()
        self._run()
        self._todos(player).with_user(self.tp_creator).sudo().action_feedback(feedback='later')
        self._run()
        self.assertFalse(self._todos(player))

    def test_cancelled_not_recreated(self):
        player = self._player()
        self._run()
        self._todos(player).unlink()
        self._run()
        self.assertFalse(self._todos(player))

    # -- AC-4 assignee ---------------------------------------------------------
    def test_assignee_tp_creator_on_team(self):
        player = self._player(creator=self.tp_creator)
        self._run()
        self.assertEqual(self._todos(player).user_id, self.tp_creator)

    def test_assignee_coach_creator_goes_to_head_therapist(self):
        player = self._player(creator=self.coach)
        self._run()
        self.assertEqual(self._todos(player).user_id, self.head_therapist)

    def test_assignee_inactive_tp_creator_goes_to_team_therapist(self):
        self.tp_creator.active = False
        player = self._player(creator=self.tp_creator)
        self._run()
        self.assertEqual(self._todos(player).user_id, self.head_therapist)

    def test_assignee_tp_not_on_team_goes_to_team_therapist(self):
        player = self._player(creator=self.outsider_tp)
        self._run()
        self.assertEqual(self._todos(player).user_id, self.head_therapist)

    def test_assignee_no_team_therapist_falls_back_to_clinic_admin(self):
        player = self._player(creator=self.coach, teams=self.team_nostaff)
        self._run()
        self.assertEqual(self._todos(player).user_id, self.clinic_admin)

    def test_assignee_player_without_team_goes_to_clinic_admin(self):
        player = self._player(creator=self.tp_creator, teams=self.env['sports.team'])
        self._run()
        self.assertEqual(self._todos(player).user_id, self.clinic_admin)

    def test_assignee_clinic_admin_creator(self):
        player = self._player(creator=self.clinic_admin, teams=self.env['sports.team'])
        self._run()
        self.assertEqual(self._todos(player).user_id, self.clinic_admin)

    def test_system_creator_skipped(self):
        player = self._player(creator=self.env.ref('base.user_root'))
        self._run()
        self.assertFalse(self._todos(player))

    def test_archived_assignee_is_replaced(self):
        player = self._player(creator=self.tp_creator)
        self._run()
        todo = self._todos(player)
        self.tp_creator.active = False
        self._run()
        self.assertEqual(todo.user_id, self.head_therapist)

    # -- AC-5 language -------------------------------------------------------------
    def test_french_text_for_fr_ca_assignee(self):
        self.tp_creator.lang = 'fr_CA'
        player = self._player(creator=self.tp_creator)
        self._run()
        todo = self._todos(player)
        self.assertEqual(todo.summary, 'Compléter la fiche du joueur')
        for label in ('Date de naissance',
                      "Contact d'urgence avec un numéro de téléphone",
                      'Courriel du joueur', 'Téléphone du joueur'):
            self.assertIn(label, self._text(todo))

    def test_english_text_for_en_assignee(self):
        player = self._player(creator=self.tp_creator)
        self._run()
        self.assertEqual(self._todos(player).summary, "Complete the player's file")


@tagged('post_install', '-at_install')
class TestIncompletePlayerTodoPortal1628(IncompleteTodoCommon):

    # -- AC-6 visibility ---------------------------------------------------------------
    def test_todo_visible_in_assignee_my_activities(self):
        player = self._player(creator=self.coach, name='Visible1628')
        self._run()
        self.assertEqual(self._todos(player).user_id, self.head_therapist)
        self.authenticate('it.headtherapist@example.com', 'it.headtherapist')
        resp = self.url_open('/my/activities')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Complete the player&#39;s file", resp.text)
        self.assertIn('Visible1628', resp.text)
