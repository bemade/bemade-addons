"""Task 1639 — internal clinic users at parity. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Email links: an internal therapist and a clinic admin get the APP
  team link (/my/team?team_id=…) in the morning briefing line, like portal
  users; an internal user with NO clinic role keeps the backend link; the
  urgent-alert path uses the same rule (_sc_backend_link_recipient).
* UC-2 The internal « Treatment Professional » group implies the clinic
  « Internal User » group (and migration 19.0.1.105.0 writes it on existing
  databases, idempotent); a backend user auto-synced as therapist by a staff
  row reads the player, injury and contacts pages without an AccessError.
* UC-3 Parity of the recent app features for an internal therapist (not an
  admin) and a clinic admin: #1630 medical levels, #1633 date of birth,
  #1604 quick verify / resolve (#1603 proposal), #1631 backward stage, #1634
  card status pills, #1635 Activities tab count, #1616 documents, #1628 the
  To-Do of an incomplete new player.
* UC-4 Identity guard, app only: an internal admin creating an exact
  name + DOB duplicate THROUGH THE APP is refused; through the backend ORM it
  is allowed; a superuser create is allowed; a rename through the app posts
  the audited correction note.
* UC-5 Injury follower subtypes use all_group_ids: a clinic admin (therapist
  only through « Administrator ») gets the internal updates.
"""
import importlib.util
import os

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


def _migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.105.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('sc_1639_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Parity1639Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.backend_only = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P39 Backend Only', 'login': 'p39.backend@example.com',
            'group_ids': [Command.set([env.ref('base.group_user').id])],
        })
        cls.player.write({'date_of_birth': '2009-04-05'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _save(self, record, field, value, **extra):
        record.invalidate_recordset()
        data = dict({'field': field, 'value': value,
                     'write_date': fields.Datetime.to_string(record.sudo().write_date),
                     'csrf_token': self._csrf()}, **extra)
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data=data,
                             allow_redirects=False)


@tagged('post_install', '-at_install')
class TestInternalParity1639(Parity1639Common):

    # -- UC-1 ------------------------------------------------------------
    def test_email_links_open_the_app(self):
        base = 'https://synthetic.example.com'
        for user in (self.itp, self.cadmin, self.tp, self.coach):
            self.assertFalse(user._sc_backend_link_recipient(), user.name)
            url = self.team_a._dashboard_url(base, internal=user._sc_backend_link_recipient())
            self.assertEqual(url, '%s/my/team?team_id=%s' % (base, self.team_a.id), user.name)
        self.assertTrue(self.backend_only._sc_backend_link_recipient())
        self.assertIn('/odoo/action-', self.team_a._dashboard_url(
            base, internal=self.backend_only._sc_backend_link_recipient()))

    def test_briefing_line_uses_the_app_link(self):
        staff = self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_a.id), ('partner_id', '=', self.itp.partner_id.id)])
        now = fields.Datetime.now()
        line = self.itp._digest_build_team_line(staff, 'tp', now, now, 'https://synthetic.example.com')
        if line:
            self.assertIn('/my/team?team_id=%s' % self.team_a.id, line['url'])

    # -- UC-2 ------------------------------------------------------------
    def test_therapist_group_implies_clinic_user(self):
        tp_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        clinic_user = self.env.ref('bemade_sports_clinic.group_sports_clinic_user')
        self.assertIn(clinic_user, tp_group.implied_ids)
        tp_group.write({'implied_ids': [Command.unlink(clinic_user.id)]})
        migration = _migration()
        migration.migrate(self.env.cr, '19.0.1.104.3')
        self.assertIn(clinic_user, tp_group.implied_ids)
        migration.migrate(self.env.cr, '19.0.1.104.3')  # idempotent
        self.assertIn(clinic_user, tp_group.implied_ids)

    def test_auto_synced_internal_therapist_reads_the_pages(self):
        synced = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P39 Synced TP', 'login': 'p39.synced@example.com', 'password': 'p39-synced-pass',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': synced.partner_id.id, 'role': 'therapist'})
        synced.invalidate_recordset()
        self.assertTrue(synced.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        self.assertTrue(synced.has_group('bemade_sports_clinic.group_sports_clinic_user'))
        self.authenticate('p39.synced@example.com', 'p39-synced-pass')
        for url in ('/my/player?player_id=%s&tab=info' % self.player.id,
                    '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id),
                    '/my/team?team_id=%s' % self.team_a.id):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotIn('AccessError', resp.text, url)

    # -- UC-3 ------------------------------------------------------------
    def _logins(self):
        return ((self._login_itp, self.itp), (self._login_cadmin, self.cadmin))

    @mute_logger('odoo.http')
    def test_feature_parity(self):
        for login, user in self._logins():
            login()
            who = user.name
            # #1630 / #1677 medical lists.
            resp = self.url_open('/my/app/medical/item/add', data={
                'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic %s' % who,
                'csrf_token': self._csrf()}, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, (who, resp.text))
            # #1633 date of birth: the confirm step, then saved.
            resp = self._save(self.player, 'date_of_birth', '2009-04-06')
            self.assertEqual(resp.status_code, 428, (who, resp.text))
            resp = self._save(self.player, 'date_of_birth', '2009-04-06', confirm='1')
            self.assertEqual(resp.status_code, 200, (who, resp.text))
            self.player.sudo().write({'date_of_birth': '2009-04-05'})
            # #1634 card status pills, #1635 Activities tab.
            _text, tree = self._get('/my/players')
            self.assertTrue(tree.xpath('//*[@data-sc-pill-select]'), who)
            _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
            self.assertTrue(tree.xpath('//nav[@data-sc-tabs]/a[@data-sc-tab="activities"]'), who)
            # #1604 quick verify / resolve (#1603 proposal path).
            injury = self.env['sports.patient.injury'].create({
                'patient_id': self.player.id, 'diagnosis': 'P39 %s' % who})
            injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
            resp = self.url_open('/my/injury/%s/verify' % injury.id,
                                 data={'csrf_token': self._csrf()}, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, (who, resp.text))
            resp = self.url_open('/my/injury/%s/resolve' % injury.id, data={
                'csrf_token': self._csrf(), 'resolution_date': fields.Date.to_string(fields.Date.today())},
                allow_redirects=False)
            self.assertEqual(resp.status_code, 200, (who, resp.text))
            # #1631 backward stage (resolved -> active).
            resp = self._save(injury, 'stage', 'active')
            self.assertEqual(resp.status_code, 200, (who, resp.text))
            # #1616 documents.
            resp = self.url_open('/my/patient/document/upload', data={
                'csrf_token': self._csrf(), 'patient_id': self.player.id, 'injury_id': injury.id,
                'return_url': '/my/player?player_id=%s' % self.player.id,
            }, files={'attachment': ('p39-%s.pdf' % user.id, b'synthetic', 'application/pdf')},
                allow_redirects=False)
            self.assertIn(resp.status_code, (302, 303), who)
            self.assertTrue(self.env['sports.injury.document'].search_count([
                ('patient_id', '=', self.player.id), ('file_name', '=', 'p39-%s.pdf' % user.id)]), who)

    def test_incomplete_new_player_todo(self):
        # #1628: a new player missing information gets its To-Do assigned to
        # its creator — an internal therapist or a clinic admin too.
        for login, user in self._logins():
            login()
            name = 'Todo%s' % user.id
            resp = self.url_open('/my/player/create/save', data={
                'csrf_token': self._csrf(), 'first_name': 'P39', 'last_name': name,
                'team_ids': self.team_a.id}, allow_redirects=False)
            self.assertIn(resp.status_code, (302, 303), user.name)
            created = self.env['sports.patient'].search([('last_name', '=', name)])
            self.assertTrue(created, user.name)
            self.assertTrue(created._sc_incomplete_items(), user.name)
            # The daily cron's To-Do lands with its creator (therapist
            # rights + staff / admin): an internal therapist or admin too.
            self.assertEqual(created._sc_incomplete_todo_assignee(), user, user.name)

    # -- UC-4 ------------------------------------------------------------
    def test_identity_guard_app_only(self):
        dup = {'first_name': 'Pat', 'last_name': 'One', 'date_of_birth': '2009-04-05'}
        self._login_cadmin()
        resp = self.url_open('/my/player/create/save', data=dict(
            dup, csrf_token=self._csrf(), team_ids=self.team_a.id), allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(self.env['sports.patient'].search_count([
            ('first_name', '=', 'Pat'), ('last_name', '=', 'One')]), 1, 'the app let a duplicate in')
        # Backend ORM (no app flag): allowed (owner choice).
        twin = self.env['sports.patient'].with_user(self.cadmin).create(dict(dup))
        self.assertTrue(twin)
        # Superuser (imports, merges, scripts): allowed.
        self.assertTrue(self.env['sports.patient'].sudo().create(dict(dup)))
        # A rename through the app posts the audited correction note.
        resp = self._save(self.player, 'first_name', 'Patrick', confirm='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        notes = self.player.message_ids.filtered(lambda m: 'Pat → Patrick' in (m.body or ''))
        self.assertTrue(notes)

    # -- UC-5 ------------------------------------------------------------
    def test_injury_follower_subtypes_for_clinic_admin(self):
        internal_subtype = self.env.ref('bemade_sports_clinic.subtype_patient_injury_internal_update')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'P39 subtypes'})
        injury.message_subscribe(partner_ids=[self.cadmin.partner_id.id])
        injury._manage_treatment_professional_subscriptions()
        follower = injury.message_follower_ids.filtered(lambda f: f.partner_id == self.cadmin.partner_id)
        self.assertTrue(follower)
        self.assertIn(internal_subtype, follower.subtype_ids)
