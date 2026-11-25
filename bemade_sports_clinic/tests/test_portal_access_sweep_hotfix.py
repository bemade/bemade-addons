"""Security hotfix 19.0.1.42.5 (forward-port 19.0.1.99.3) — portal ACL /
record-rule sweep.

A sweep of the portal ACLs and record rules on prod found four gaps.

Acceptance criteria:

1. Emergency contacts (sports.patient.contact): a portal treatment
   professional reads only the contacts of patients on teams they staff;
   another team's contacts are out of search results and a direct read raises
   AccessError. The coach rule is unchanged.
2. Injury documents (sports.injury.document): a coach cannot read the
   documents of an injury flagged hidden_from_coaches; a portal TP still can.
   Documents of a visible injury and patient-level documents (no injury) stay
   readable by both. Another team's documents stay out of reach of both.
3. Team staff (sports.team.staff): a portal user (role « other » staff,
   coach, TP) reads only the staff rows of teams they staff; a portal user
   staffing no team reads none. The portal pages that show staff still render:
   player page, team page, events list / calendar / event page (TP, incl. an
   event of a team they do not staff), event edit form, activities list.
4. Players (sports.patient): a plain portal user (role « other » staff) can no
   longer write or create a player over RPC (read unchanged). A coach still
   edits a player through /my/player/save and creates one through
   /my/player/create/save (the team-page create routes are TP-only), and
   through the app autosave route /my/app/save (position, jersey number,
   date of birth since #1633). Role « other » staff hold no app role there
   (403, unchanged).
5. Internal users are unchanged (clinic admin reads every contact / document
   / staff row; internal clinic user still writes players).
6. The narrowed portal injury-document rule carries the new domain (the XML
   of a fresh install; existing databases get it from the 19.0.1.99.3
   post-migrate, which uses the identical string).
"""
import base64
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon

FILE = base64.b64encode(b'synthetic hotfix document')
NEW_DOC_DOMAIN = (
    "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id), '|', "
    "('injury_id', '=', False), ('injury_id.hidden_from_coaches', '=', False)]"
)


@tagged('-at_install', 'post_install')
class TestPortalAccessSweepHotfix(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Users = env['res.users'].with_context(no_reset_password=True)
        portal = env.ref('base.group_portal').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        # Team-A staffer with role « other »: portal group only.
        cls.other_staff = Users.create({
            'name': 'Sweep Other', 'login': 'sweep.other@example.com',
            'password': 'sweep-other', 'group_ids': [Command.set([portal])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.other_staff.partner_id.id,
            'role': 'other',
        })
        # A team-B coach, so team B has a staff row nobody on team A staffs.
        cls.coach_b = Users.create({
            'name': 'Sweep Coach B', 'login': 'sweep.coachb@example.com',
            'password': 'sweep-coachb', 'group_ids': [Command.set([portal, coach_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.coach_b.partner_id.id,
            'role': 'coach',
        })
        cls.staff_a = env['sports.team.staff'].search([('team_id', '=', cls.team_a.id)])
        cls.staff_b = env['sports.team.staff'].search([('team_id', '=', cls.team_b.id)])

        # Contacts: team A (from the common fixture) and team B.
        cls.contact_b = env['sports.patient.contact'].create({
            'patient_id': cls.player_b.id, 'name': 'Parent Two', 'contact_type': 'father',
        })

        # Injury documents on team A: visible injury, hidden injury, patient-level.
        cls.hidden_injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Hidden thing',
            'hidden_from_coaches': True,
        })
        Doc = env['sports.injury.document']

        def _doc(name, patient, injury=False):
            return Doc.create({
                'name': name, 'patient_id': patient.id,
                'injury_id': injury.id if injury else False,
                'file_content': FILE, 'file_name': name + '.txt',
            })
        cls.doc_visible = _doc('sweep-visible', cls.player, cls.injury)
        cls.doc_hidden = _doc('sweep-hidden', cls.player, cls.hidden_injury)
        cls.doc_patient = _doc('sweep-patient', cls.player)
        cls.doc_team_b = _doc('sweep-team-b', cls.player_b)
        cls.all_docs = cls.doc_visible | cls.doc_hidden | cls.doc_patient | cls.doc_team_b

        # A team-B event the team-A TP does not staff (TPs see every event).
        start = datetime(2026, 2, 3, 10, 0)
        cls.event_b = env['sports.event'].create({
            'name': 'Sweep Event B', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_b.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'state': 'confirmed',
        })

        def _internal(login, group_xmlid):
            return Users.create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [Command.set([
                    env.ref('base.group_user').id, env.ref(group_xmlid).id])],
            })
        cls.int_user = _internal(
            'sweep.int.user', 'bemade_sports_clinic.group_sports_clinic_user')
        cls.int_admin = _internal(
            'sweep.int.admin', 'bemade_sports_clinic.group_sports_clinic_admin')

    def _as(self, model, user):
        return self.env[model].with_user(user)

    def _get_ok(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertNotIn('Traceback', resp.text, url)
        return resp

    # ------------------------------------------------------------------
    # 1. emergency contacts
    # ------------------------------------------------------------------
    def test_portal_tp_reads_only_staffed_team_contacts(self):
        Contact = self._as('sports.patient.contact', self.tp)
        both = self.contact | self.contact_b
        self.assertEqual(Contact.search([('id', 'in', both.ids)]), self.contact)
        Contact.browse(self.contact.id).read(['name', 'mobile', 'email'])
        with mute_logger('odoo.addons.base.models.ir_rule'), \
                self.assertRaises(AccessError):
            Contact.browse(self.contact_b.id).read(['name'])

    def test_portal_tp_cannot_write_other_team_contact(self):
        with mute_logger('odoo.addons.base.models.ir_rule'), \
                self.assertRaises(AccessError):
            self._as('sports.patient.contact', self.tp).browse(
                self.contact_b.id).write({'name': 'x'})

    def test_coach_contacts_unchanged(self):
        Contact = self._as('sports.patient.contact', self.coach)
        both = self.contact | self.contact_b
        self.assertEqual(Contact.search([('id', 'in', both.ids)]), self.contact)

    # ------------------------------------------------------------------
    # 2. injury documents
    # ------------------------------------------------------------------
    def test_coach_cannot_read_hidden_injury_documents(self):
        Doc = self._as('sports.injury.document', self.coach)
        found = Doc.search([('id', 'in', self.all_docs.ids)])
        self.assertEqual(found, self.doc_visible | self.doc_patient)
        found.read(['name', 'file_name'])
        with mute_logger('odoo.addons.base.models.ir_rule'):
            with self.assertRaises(AccessError):
                Doc.browse(self.doc_hidden.id).read(['name'])
            with self.assertRaises(AccessError):
                Doc.browse(self.doc_team_b.id).read(['name'])

    def test_other_role_staff_cannot_read_hidden_injury_documents(self):
        Doc = self._as('sports.injury.document', self.other_staff)
        self.assertEqual(Doc.search([('id', 'in', self.all_docs.ids)]),
                         self.doc_visible | self.doc_patient)

    def test_portal_tp_reads_hidden_injury_documents(self):
        Doc = self._as('sports.injury.document', self.tp)
        found = Doc.search([('id', 'in', self.all_docs.ids)])
        self.assertEqual(found, self.doc_visible | self.doc_hidden | self.doc_patient)
        found.read(['name', 'file_name'])
        with mute_logger('odoo.addons.base.models.ir_rule'), \
                self.assertRaises(AccessError):
            Doc.browse(self.doc_team_b.id).read(['name'])

    def test_portal_document_rule_domain(self):
        rule = self.env.ref('bemade_sports_clinic.portal_injury_document_access')
        self.assertEqual(rule.domain_force, NEW_DOC_DOMAIN)

    def test_coach_document_download_routes(self):
        self._login_coach()
        resp = self.url_open(f'/my/injury/document/download/{self.doc_visible.id}')
        self.assertEqual(resp.status_code, 200)
        resp = self.url_open(f'/my/injury/document/download/{self.doc_hidden.id}')
        self.assertNotEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    # 3. team staff
    # ------------------------------------------------------------------
    def test_portal_users_read_only_own_team_staff(self):
        every = self.staff_a | self.staff_b
        for user in (self.other_staff, self.coach, self.tp):
            with self.subTest(user=user.login):
                Staff = self._as('sports.team.staff', user)
                self.assertEqual(Staff.search([('id', 'in', every.ids)]), self.staff_a)
                with mute_logger('odoo.addons.base.models.ir_rule'), \
                        self.assertRaises(AccessError):
                    Staff.browse(self.staff_b.ids).read(['name', 'email'])
        self.assertEqual(self._as('sports.team.staff', self.coach_b).search(
            [('id', 'in', every.ids)]), self.staff_b)
        self.assertFalse(self._as('sports.team.staff', self.plain).search([]))

    def test_coach_pages_render(self):
        self._login_coach()
        self._get_ok(f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self._get_ok(f'/my/team/{self.team_a.id}')
        self._get_ok('/my/teams')
        self._get_ok('/my/players')
        self._get_ok('/my/activities')
        self._get_ok('/my/events')
        self._get_ok(f'/my/event/{self.event.id}')

    def test_other_role_staff_pages_render(self):
        self.authenticate('sweep.other@example.com', 'sweep-other')
        self._get_ok(f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self._get_ok(f'/my/team/{self.team_a.id}')
        self._get_ok('/my/teams')

    def test_portal_tp_pages_render(self):
        self._login_tp()
        self._get_ok(f'/my/player?player_id={self.player.id}&team_id={self.team_a.id}')
        self._get_ok(f'/my/team/{self.team_a.id}')
        self._get_ok('/my/activities')
        self._get_ok('/my/events')
        self._get_ok('/my/events/calendar/data')
        self._get_ok(f'/my/event/{self.event.id}')
        # An event of a team the TP does not staff (TPs see every event).
        self._get_ok(f'/my/event/{self.event_b.id}')
        self._get_ok(f'/my/event/{self.event_b.id}/edit')
        self._get_ok('/my/event/create')
        self._get_ok('/my')
        self._get_ok('/my/clinics')
        self._get_ok('/my/notepad')
        self._get_ok('/my/app/more')
        self._get_ok(f'/my/player?player_id={self.player.id}&tab=info')

    def test_portal_tp_event_assignee_picker_lists_every_professional(self):
        # The picker is fed by a sudo helper, so the staff rule does not
        # collapse it to the TP's own teams.
        self.env['sports.team.staff'].create({
            'team_id': self.team_b.id, 'partner_id': self.int_admin.partner_id.id,
            'role': 'therapist',
        })
        self._login_tp()
        resp = self._get_ok(f'/my/event/{self.event_b.id}/edit')
        self.assertIn(self.int_admin.name, resp.text)

    # ------------------------------------------------------------------
    # 4. players: write / create
    # ------------------------------------------------------------------
    def test_plain_portal_staff_cannot_write_or_create_players(self):
        Patient = self._as('sports.patient', self.other_staff)
        self.assertEqual(Patient.search([('id', '=', self.player.id)]), self.player)
        Patient.browse(self.player.id).read(['first_name'])
        with mute_logger('odoo.addons.base.models.ir_model'):
            with self.assertRaises(AccessError):
                # position, not a name: a name change hits the #1600
                # identity guard (UserError) before the ACL check.
                Patient.browse(self.player.id).write({'position': 'Hacked'})
            with self.assertRaises(AccessError):
                Patient.create({'first_name': 'Rogue', 'last_name': 'Player'})
        self.assertNotEqual(self.player.position, 'Hacked')

    def test_plain_portal_staff_edit_route_writes_nothing(self):
        self.authenticate('sweep.other@example.com', 'sweep-other')
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'first_name': 'Pat', 'last_name': 'One', 'position': 'Hacked',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.player.invalidate_recordset()
        self.assertNotEqual(self.player.position, 'Hacked')

    def test_coach_orm_write_still_allowed(self):
        self._as('sports.patient', self.coach).browse(self.player.id).write(
            {'position': 'Goalie'})
        self.assertEqual(self.player.position, 'Goalie')
        with mute_logger('odoo.addons.base.models.ir_rule'), \
                self.assertRaises(AccessError):
            self._as('sports.patient', self.coach).browse(self.player_b.id).write(
                {'position': 'Goalie'})

    def test_coach_edits_player_through_save_route(self):
        self._login_coach()
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            # Same names: a name change on the legacy form is the #1600
            # confirmed identity correction (covered by its own tests).
            'first_name': 'Pat', 'last_name': 'One',
            'position': 'Winger',
        })
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.position, 'Winger')

    def test_coach_creates_player_through_create_route(self):
        self._login_coach()
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'SweepCoach', 'last_name': 'Created',
            'date_of_birth': '2009-01-02',
        }, allow_redirects=False)
        # 303 to the new player's page (a standalone coach create assigns no
        # team, so that page is outside the coach's scope — unchanged).
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(self.env['sports.patient'].search([
            ('first_name', '=', 'SweepCoach'), ('last_name', '=', 'Created')]))
        # The team-page create routes are TP-only at this version (unchanged).

    def _app_save(self, patient, field, value, **extra):
        patient.invalidate_recordset()
        return self.url_open('/my/app/save/sports.patient/%s' % patient.id, data={
            'field': field, 'value': value,
            'write_date': fields.Datetime.to_string(patient.write_date),
            'csrf_token': self._csrf(), **extra,
        }, allow_redirects=False)

    def test_coach_edits_player_through_app_save(self):
        self._login_coach()
        for field, value in (('position', 'Centre'), ('jersey_number', '17'),
                             ('date_of_birth', '2008-05-06')):
            with self.subTest(field=field):
                resp = self._app_save(self.player, field, value)
                self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.position, 'Centre')
        self.assertEqual(self.player.jersey_number, '17')
        self.assertEqual(str(self.player.date_of_birth), '2008-05-06')
        # Another team's player stays out of reach.
        resp = self._app_save(self.player_b, 'position', 'Centre')
        self.assertEqual(resp.status_code, 403)

    def test_plain_portal_staff_app_save_refused(self):
        self.authenticate('sweep.other@example.com', 'sweep-other')
        resp = self._app_save(self.player, 'position', 'Hacked')
        self.assertEqual(resp.status_code, 403)
        self.player.invalidate_recordset()
        self.assertNotEqual(self.player.position, 'Hacked')

    def test_coach_app_pages_render(self):
        self._login_coach()
        self._get_ok('/my')
        self._get_ok('/my/app/more')
        self._get_ok(f'/my/player?player_id={self.player.id}&tab=info')

    # ------------------------------------------------------------------
    # 5. internal users unchanged
    # ------------------------------------------------------------------
    def test_internal_admin_reads_everything(self):
        both_contacts = self.contact | self.contact_b
        self.assertEqual(self._as('sports.patient.contact', self.int_admin).search(
            [('id', 'in', both_contacts.ids)]), both_contacts)
        self.assertEqual(self._as('sports.injury.document', self.int_admin).search(
            [('id', 'in', self.all_docs.ids)]), self.all_docs)
        every = self.staff_a | self.staff_b
        for user in (self.int_admin, self.int_user):
            with self.subTest(user=user.login):
                self.assertEqual(self._as('sports.team.staff', user).search(
                    [('id', 'in', every.ids)]), every)

    def test_internal_clinic_user_still_writes_players(self):
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': self.int_user.partner_id.id,
            'role': 'other',
        })
        self._as('sports.patient', self.int_user).browse(self.player.id).write(
            {'position': 'Defence'})
        self.assertEqual(self.player.position, 'Defence')
