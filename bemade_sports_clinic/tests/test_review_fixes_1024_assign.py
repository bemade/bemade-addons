"""Review fixes 2026-10-24 (adversarial review) — event assignees.
Synthetic fixtures only.

Acceptance criteria:

* AC-1 (HIGH, assignee escalation) Only a treatment professional (portal or
  internal TP group) can be assigned to an event: the ORM refuses any other
  user (superuser included), and so does every portal route (create, save,
  the app's inline field) BEFORE its sudo write — no assignment, no coverage
  staff row and no group is created, and the refusal is a clean message.
* AC-2 A legitimate assignment (a TP covering an event of a team the
  assigner staffs) still works and still opens the coverage row.
* AC-3 An event-coverage staff row (``source = 'event'``) never adds — nor
  removes — a portal group, and never counts as a therapist role.
* AC-4 (owner policy) Assigning staff to an event whose teams the assigner
  does not staff is clinic-admin only: a non-admin may set / change the
  assignees (or the teams of an event that has assignees) only when every
  team of the event is one they staff through a non-event row; otherwise
  « Only the clinic administration can assign staff to an event of a team
  you're not part of. » (ORM non-superuser writes and every route). Clinic
  and system admins are unrestricted. Creating the event itself stays open
  (without assignees).
* AC-5 The app hides the assignee picker where the user cannot assign, with
  the reason; the event form carries the guard rule (#1658) for the dynamic
  case.
* AC-6 (#1665) « Event restored » is sent only on a real restore (back to
  Confirmed), never when a cancelled event is marked invoiced.
* AC-7 The new strings render in French (fr_CA).
"""
import json
from contextlib import contextmanager
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

POLICY_EN = "Only the clinic administration can assign staff to an event of a team you're not part of."
POLICY_FR = ("Seule l'administration de la clinique peut assigner du personnel à un événement "
             "d'une équipe dont vous ne faites pas partie.")
NOT_TP_EN = "Only treatment professionals can be assigned to an event."


class AssignCommon:

    @classmethod
    def _assign_fixtures(cls):
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        cls.tp_group = tp_g
        cls.org_x = env['res.partner'].create({'name': 'RF Org X', 'is_company': True})
        cls.team_own = env['sports.team'].create({'name': 'RF Team Own', 'parent_id': cls.org_x.id})
        cls.team_other = env['sports.team'].create({'name': 'RF Team Other', 'parent_id': cls.org_x.id})
        Users = env['res.users'].with_context(no_reset_password=True)
        cls.rf_tp = Users.create({
            'name': 'RF Assigner', 'login': 'rf.assigner@example.com', 'password': 'rf-assigner',
            'group_ids': [Command.set([portal, tp_g.id])],
        })
        cls.rf_tp2 = Users.create({
            'name': 'RF Colleague', 'login': 'rf.colleague@example.com', 'password': 'rf-colleague',
            'group_ids': [Command.set([portal, tp_g.id])],
        })
        cls.rf_coach = Users.create({
            'name': 'RF Coach', 'login': 'rf.coach@example.com', 'password': 'rf-coach',
            'group_ids': [Command.set([portal, env.ref('bemade_sports_clinic.group_portal_team_coach').id])],
        })
        cls.rf_internal_tp = Users.create({
            'name': 'RF Internal TP', 'login': 'rf.internal.tp@example.com', 'password': 'rf-internal-tp',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id])],
        })
        cls.rf_admin = Users.create({
            'name': 'RF Clinic Admin', 'login': 'rf.admin@example.com', 'password': 'rf-admin',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_admin').id])],
        })
        Staff = env['sports.team.staff']
        Staff.create({'team_id': cls.team_own.id, 'partner_id': cls.rf_tp.partner_id.id, 'role': 'therapist'})
        Staff.create({'team_id': cls.team_own.id, 'partner_id': cls.rf_internal_tp.partner_id.id,
                      'role': 'therapist'})
        Staff.create({'team_id': cls.team_other.id, 'partner_id': cls.rf_tp2.partner_id.id, 'role': 'therapist'})
        Staff.create({'team_id': cls.team_other.id, 'partner_id': cls.rf_coach.partner_id.id, 'role': 'coach'})
        start = fields.Datetime.now().replace(microsecond=0) + timedelta(hours=1)
        cls.ev_own = cls._rf_event('RF Own Game', cls.team_own, start)
        cls.ev_other = cls._rf_event('RF Other Game', cls.team_other, start)

    @classmethod
    def _rf_event(cls, name, team, start, staff=None):
        return cls.env['sports.event'].create({
            'name': name, 'event_type': 'game', 'team_ids': [Command.set(team.ids)],
            'date_start': start, 'date_end': start + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set((staff or cls.env['res.users']).ids)],
        })

    @contextmanager
    def _refused(self, text):
        """assertRaises (Odoo's: in a savepoint, so a refused write is
        rolled back) + the message."""
        with self.assertRaises(ValidationError) as caught:
            yield
        self.assertIn(text, str(caught.exception))

    def _rows(self, user, team=None):
        domain = [('partner_id', '=', user.partner_id.id)]
        if team:
            domain.append(('team_id', '=', team.id))
        return self.env['sports.team.staff'].sudo().search(domain)


@tagged('post_install', '-at_install')
class TestAssigneeModel1024(AssignCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._assign_fixtures()

    # -- AC-1 (ORM) --------------------------------------------------------
    def test_orm_refuses_non_tp_assignee_even_superuser(self):
        rows_before = self._rows(self.rf_coach)
        with self._refused(NOT_TP_EN):
            self.ev_own.write({'assigned_staff_ids': [Command.link(self.rf_coach.id)]})
        with self._refused(NOT_TP_EN):
            self._rf_event('RF Crafted', self.team_own, self.ev_own.date_start, staff=self.rf_coach)
        self.ev_own.invalidate_recordset()
        self.assertFalse(self.ev_own.assigned_staff_ids)
        self.assertEqual(self._rows(self.rf_coach), rows_before)
        self.assertNotIn(self.tp_group, self.rf_coach.all_group_ids)

    def test_existing_non_tp_assignee_kept_but_never_covered(self):
        """A pre-constraint assignment stays (no data change) but gives no
        coverage row; editing other assignees does not re-check it."""
        self.env.cr.execute(
            'INSERT INTO sports_event_staff_rel (event_id, user_id) VALUES (%s, %s)',
            (self.ev_own.id, self.rf_coach.id))
        self.ev_own.invalidate_recordset()
        self.ev_own._sync_event_auto_staff()
        self.assertFalse(self._rows(self.rf_coach, self.team_own))
        self.ev_own.write({'assigned_staff_ids': [Command.link(self.rf_tp.id)]})
        self.assertEqual(self.ev_own.assigned_staff_ids, self.rf_coach | self.rf_tp)

    # -- AC-2 --------------------------------------------------------------
    def test_legit_tp_coverage_still_works(self):
        self.ev_own.with_user(self.rf_internal_tp).write(
            {'assigned_staff_ids': [Command.set(self.rf_tp2.ids)]})
        self.assertEqual(self.ev_own.assigned_staff_ids, self.rf_tp2)
        row = self._rows(self.rf_tp2, self.team_own)
        self.assertEqual((row.source, row.role, row.is_auto_created), ('event', 'therapist', True))

    # -- AC-3 --------------------------------------------------------------
    def test_event_row_grants_no_group(self):
        portal = self.env.ref('base.group_portal')
        lonely = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'RF Lonely', 'login': 'rf.lonely@example.com', 'group_ids': [Command.set(portal.ids)]})
        row = self.env['sports.team.staff'].create({
            'team_id': self.team_own.id, 'partner_id': lonely.partner_id.id, 'role': 'therapist',
            'is_auto_created': True, 'source': 'event'})
        self.assertNotIn(self.tp_group, lonely.group_ids)
        self.assertFalse(row._get_staff_with_therapist_roles(lonely.partner_id.id))
        # Adopted out of event coverage (a real staff row now): it counts.
        row.write({'source': 'manual', 'is_auto_created': False})
        self.assertIn(self.tp_group, lonely.group_ids)

    def test_event_row_removal_keeps_a_group_only_tp(self):
        """A TP holding the group with no staff row of their own keeps it
        when their coverage row goes away (it used to strip the group)."""
        portal = self.env.ref('base.group_portal')
        floater = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'RF Floater', 'login': 'rf.floater@example.com',
            'group_ids': [Command.set([portal.id, self.tp_group.id])]})
        self.ev_own.write({'assigned_staff_ids': [Command.set(floater.ids)]})
        self.assertTrue(self._rows(floater, self.team_own))
        self.ev_own.write({'assigned_staff_ids': [Command.clear()]})
        self.assertFalse(self._rows(floater, self.team_own))
        self.assertIn(self.tp_group, floater.group_ids)

    # -- AC-4 (ORM) --------------------------------------------------------
    def test_policy_own_team_allowed(self):
        self.ev_own.with_user(self.rf_internal_tp).write(
            {'assigned_staff_ids': [Command.set((self.rf_internal_tp | self.rf_tp).ids)]})
        self.assertEqual(self.ev_own.assigned_staff_ids, self.rf_internal_tp | self.rf_tp)

    def test_policy_other_team_refused(self):
        ev = self.ev_other.with_user(self.rf_internal_tp)
        with self._refused(POLICY_EN):
            ev.write({'assigned_staff_ids': [Command.link(self.rf_internal_tp.id)]})
        self.ev_other.invalidate_recordset()
        self.assertFalse(self.ev_other.assigned_staff_ids)
        self.assertFalse(self._rows(self.rf_internal_tp, self.team_other))
        # Creating another team's event (the routes create under sudo and run
        # this check first): allowed without assignees only.
        Event = self.env['sports.event']
        with self._refused(POLICY_EN):
            Event._sc_check_assignment(self.rf_internal_tp, (), self.rf_tp2.ids, (), self.team_other.ids)
        Event._sc_check_assignment(self.rf_internal_tp, (), (), (), self.team_other.ids)

    def test_policy_team_change_with_assignees_refused(self):
        # (A non-admin cannot even read a team they do not staff, so the ORM
        # write stops at the access rules; the portal routes write the teams
        # under sudo and run this same check first — see the route tests.)
        Event = self.env['sports.event']
        staff = self.rf_internal_tp.ids
        with self._refused(POLICY_EN):
            Event._sc_check_assignment(self.rf_internal_tp, staff, staff,
                                       self.team_own.ids, self.team_other.ids)
        # Without assignees the teams stay free to edit; the admin anywhere.
        Event._sc_check_assignment(self.rf_internal_tp, (), (), self.team_own.ids, self.team_other.ids)
        Event._sc_check_assignment(self.rf_admin, staff, staff, self.team_own.ids, self.team_other.ids)

    def test_event_row_does_not_make_one_part_of_the_team(self):
        self.ev_other.write({'assigned_staff_ids': [Command.set(self.rf_internal_tp.ids)]})
        self.assertEqual(self._rows(self.rf_internal_tp, self.team_other).source, 'event')
        with self._refused(POLICY_EN):
            self.ev_other.with_user(self.rf_internal_tp).write(
                {'assigned_staff_ids': [Command.link(self.rf_tp2.id)]})

    def test_policy_clinic_admin_anywhere(self):
        self.ev_other.with_user(self.rf_admin).write(
            {'assigned_staff_ids': [Command.set((self.rf_tp | self.rf_tp2).ids)]})
        self.assertEqual(self.ev_other.assigned_staff_ids, self.rf_tp | self.rf_tp2)

    # -- AC-6 --------------------------------------------------------------
    def _restored_notices(self, event, before):
        msgs = self.env['mail.message'].search(
            [('model', '=', 'sports.event'), ('res_id', '=', event.id)]) - before
        return msgs.filtered(lambda m: 'restored' in (m.subject or '').lower())

    def test_invoicing_a_cancelled_event_sends_no_restore(self):
        self.ev_own.write({'assigned_staff_ids': [Command.set(self.rf_tp.ids)]})
        self.ev_own.write({'state': 'cancelled'})
        before = self.env['mail.message'].search([('model', '=', 'sports.event'), ('res_id', '=', self.ev_own.id)])
        self.ev_own.with_user(self.rf_admin).action_mark_invoiced()
        self.assertEqual(self.ev_own.state, 'invoiced')
        self.assertFalse(self._restored_notices(self.ev_own, before))

    def test_revive_still_sends_restore(self):
        self.ev_own.write({'assigned_staff_ids': [Command.set(self.rf_tp.ids)]})
        self.ev_own.write({'state': 'cancelled'})
        before = self.env['mail.message'].search([('model', '=', 'sports.event'), ('res_id', '=', self.ev_own.id)])
        self.ev_own.with_user(self.rf_admin).action_revive()
        self.assertEqual(self.ev_own.state, 'confirmed')
        notices = self._restored_notices(self.ev_own, before)
        self.assertEqual(len(notices), 1)
        self.assertIn(self.rf_tp.partner_id, notices.notified_partner_ids)


class AssignHttpCommon(AssignCommon, AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._assign_fixtures()

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _login_rf(self):
        self.authenticate('rf.assigner@example.com', 'rf-assigner')

    def _login_admin(self):
        self.authenticate('rf.admin@example.com', 'rf-admin')

    def _post_save(self, event, staff, teams=None):
        return self.url_open('/my/event/%s/save' % event.id, data={
            'csrf_token': self._csrf(), 'name': event.name,
            'team_ids': ','.join(str(i) for i in (teams or event.team_ids).ids),
            'assigned_staff_ids': ','.join(str(i) for i in staff.ids),
        }, allow_redirects=False)

    def _post_create(self, team, staff, name='RF Route Created'):
        start = fields.Datetime.now() + timedelta(days=1)
        fmt = '%Y-%m-%dT%H:%M'
        return self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(), 'name': name, 'event_type': 'game',
            'team_ids': str(team.id), 'date_start': start.strftime(fmt),
            'date_end': (start + timedelta(hours=2)).strftime(fmt),
            'assigned_staff_ids': ','.join(str(i) for i in staff.ids),
        }, allow_redirects=False)

    def _inline(self, event, field, value):
        event.invalidate_recordset()
        return self.url_open('/my/app/save/sports.event/%s' % event.id, data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(event.write_date)}, allow_redirects=False)

    def _tree(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)


@tagged('post_install', '-at_install')
class TestAssigneeRoutes1024(AssignHttpCommon):

    def _assert_no_escalation(self):
        self.assertFalse(self._rows(self.rf_coach, self.team_own))
        self.rf_coach.invalidate_recordset()
        self.assertNotIn(self.tp_group, self.rf_coach.all_group_ids)

    # -- AC-1 (routes) -----------------------------------------------------
    def test_save_route_refuses_non_tp(self):
        self._login_rf()
        resp = self._post_save(self.ev_own, self.rf_coach)
        self.assertIn('/my/event/%s/edit?error=' % self.ev_own.id, resp.headers['Location'])
        self.assertIn('treatment+professionals', resp.headers['Location'].replace('%20', '+'))
        self.ev_own.invalidate_recordset()
        self.assertFalse(self.ev_own.assigned_staff_ids)
        self._assert_no_escalation()

    def test_create_route_refuses_non_tp(self):
        self._login_rf()
        count = self.env['sports.event'].search_count([])
        resp = self._post_create(self.team_own, self.rf_coach)
        self.assertTrue(resp.headers['Location'].endswith('/my/event/create'))
        self.assertEqual(self.env['sports.event'].search_count([]), count)
        self._assert_no_escalation()
        self.assertIn(NOT_TP_EN, self.url_open('/my/event/create').text)

    def test_inline_field_refuses_non_tp(self):
        self._login_rf()
        resp = self._inline(self.ev_own, 'assigned_staff_ids', str(self.rf_coach.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn(NOT_TP_EN, resp.text)
        self.ev_own.invalidate_recordset()
        self.assertFalse(self.ev_own.assigned_staff_ids)
        self._assert_no_escalation()

    # -- AC-2 / AC-4 (routes) ----------------------------------------------
    def test_own_team_assign_via_routes(self):
        self._login_rf()
        resp = self._post_save(self.ev_own, self.rf_tp | self.rf_tp2)
        self.assertIn('success=1', resp.headers['Location'])
        self.ev_own.invalidate_recordset()
        self.assertEqual(self.ev_own.assigned_staff_ids, self.rf_tp | self.rf_tp2)
        self.assertEqual(self._rows(self.rf_tp2, self.team_own).source, 'event')
        self.assertEqual(self._inline(self.ev_own, 'assigned_staff_ids', str(self.rf_tp.id)).status_code, 200)
        self.ev_own.invalidate_recordset()
        self.assertEqual(self.ev_own.assigned_staff_ids, self.rf_tp)
        resp = self._post_create(self.team_own, self.rf_tp2)
        self.assertIn('created=1', resp.headers['Location'])

    def test_other_team_refused_via_routes(self):
        self._login_rf()
        resp = self._post_save(self.ev_other, self.rf_tp)
        self.assertIn('/edit?error=', resp.headers['Location'])
        resp = self._inline(self.ev_other, 'assigned_staff_ids', str(self.rf_tp.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn(POLICY_EN, resp.text)
        self.ev_other.invalidate_recordset()
        self.assertFalse(self.ev_other.assigned_staff_ids)
        self.assertFalse(self._rows(self.rf_tp, self.team_other))
        # Create on another team: refused with assignees, allowed without.
        count = self.env['sports.event'].search_count([])
        resp = self._post_create(self.team_other, self.rf_tp2)
        self.assertTrue(resp.headers['Location'].endswith('/my/event/create'))
        self.assertEqual(self.env['sports.event'].search_count([]), count)
        self.assertIn(POLICY_EN, self.url_open('/my/event/create').text.replace('&#39;', "'"))
        resp = self._post_create(self.team_other, self.env['res.users'], name='RF Bare')
        self.assertIn('created=1', resp.headers['Location'])
        # Editing such an event without touching its staff stays open.
        self.ev_other.write({'assigned_staff_ids': [Command.set(self.rf_tp2.ids)]})
        resp = self._post_save(self.ev_other, self.rf_tp2)
        self.assertIn('success=1', resp.headers['Location'])
        # Moving an event with assignees onto a team one does not staff: refused.
        self.ev_own.write({'assigned_staff_ids': [Command.set(self.rf_tp.ids)]})
        resp = self._inline(self.ev_own, 'team_ids', str(self.team_other.id))
        self.assertEqual(resp.status_code, 400)
        self.ev_own.invalidate_recordset()
        self.assertEqual(self.ev_own.team_ids, self.team_own)

    def test_clinic_admin_assigns_anywhere_via_routes(self):
        self._login_admin()
        resp = self._post_save(self.ev_other, self.rf_tp)
        self.assertIn('success=1', resp.headers['Location'])
        self.ev_other.invalidate_recordset()
        self.assertEqual(self.ev_other.assigned_staff_ids, self.rf_tp)

    # -- AC-5 --------------------------------------------------------------
    def test_app_hides_picker_with_reason(self):
        self._login_rf()
        tree = self._tree('/my/event/%s' % self.ev_other.id)
        edit = tree.xpath('//*[@data-sc-edit-card="event"]//*[@data-sc-edit-view="edit"]')[0]
        props = [json.loads(p) for p in edit.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]
        self.assertNotIn('assigned_staff_ids', {p['field'] for p in props})
        self.assertIn('team_ids', {p['field'] for p in props})
        reason = edit.xpath('.//*[@data-sc-event-staff-locked]//*[@data-sc-assign-reason]')
        self.assertEqual(reason[0].text_content().strip(), POLICY_EN)
        # Own team: the picker is there, no reason.
        tree = self._tree('/my/event/%s' % self.ev_own.id)
        edit = tree.xpath('//*[@data-sc-edit-card="event"]//*[@data-sc-edit-view="edit"]')[0]
        props = [json.loads(p) for p in edit.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]
        self.assertIn('assigned_staff_ids', {p['field'] for p in props})
        self.assertFalse(edit.xpath('.//*[@data-sc-event-staff-locked]'))

    def test_create_form_guard_rule(self):
        self._login_rf()
        tree = self._tree('/my/event/create')
        form = tree.xpath('//form[@data-sc-event-form]')[0]
        rules = json.loads(form.get('data-sc-guard-rules'))
        assign = [r for r in rules if r['type'] == 'assign']
        self.assertEqual(len(assign), 1)
        self.assertEqual(assign[0]['allowed'], [self.team_own.id])
        self.assertEqual((assign[0]['staff'], assign[0]['teams']), ('assigned_staff_ids', 'team_ids'))
        self.assertEqual(form.xpath('.//*[@data-sc-guard-msg="assign"]')[0].text_content(), POLICY_EN)
        self.assertEqual({r['type'] for r in rules} - {'assign'}, {'after'})
        # A clinic admin: no rule, the picker.
        self._login_admin()
        tree = self._tree('/my/event/create')
        form = tree.xpath('//form[@data-sc-event-form]')[0]
        self.assertFalse([r for r in json.loads(form.get('data-sc-guard-rules')) if r['type'] == 'assign'])
        self.assertTrue(form.xpath('.//*[@data-sc-event-pick="staff"]'))


@tagged('post_install', '-at_install')
class TestAssigneeI18n1024(AssignHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('fr_CA')
        cls.env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if cls.env['ir.module.module']._get('website').state == 'installed':
            fr_lang = cls.env['res.lang']._lang_get('fr_CA')
            for website in cls.env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.rf_tp.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'")

    def test_new_strings_in_french(self):
        self._login_rf()
        self.assertIn(POLICY_FR, self._fr('/my/event/%s' % self.ev_other.id))
        text = self._fr('/my/event/create')
        self.assertIn('data-sc-guard-msg="assign">%s</span>' % POLICY_FR, text)
        Event = self.env['sports.event'].with_context(lang='fr_CA')
        with self._refused("Seule l'administration de la clinique"):
            Event._sc_check_assignment(self.rf_tp, (), self.rf_tp2.ids, (), self.team_other.ids)
        with self._refused('Seuls des professionnels de la santé'):
            Event._sc_check_assignment(None, (), self.rf_coach.ids, (), self.team_own.ids)
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        with mute_logger('odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            resp = self._inline(self.ev_other, 'assigned_staff_ids', str(self.rf_tp.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Seule l'administration de la clinique", json.dumps(resp.json(), ensure_ascii=False))


@tagged('post_install', '-at_install')
class TestAssigneeTour1024(AssignHttpCommon):
    browser_size = '390x844'

    def test_event_form_assign_guard(self):
        self.start_tour('/my/event/create?x1024=%s,%s,%s' % (
            self.team_own.id, self.team_other.id, self.rf_tp2.id),
            'sc_1024_event_assign', login='rf.assigner@example.com')
        self.assertFalse(self.env['sports.event'].search_count([('name', '=', 'Synthetic game 1024')]))
