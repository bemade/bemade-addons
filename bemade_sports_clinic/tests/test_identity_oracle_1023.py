"""Security review 2026-10-23 — the identity duplicate guard and the « date-
of-birth oracle » (19.0.1.107.1). Synthetic fixtures only.

REWRITTEN by task 1716 (owner decision 2026-10-26, after discussion with
MC): the DOB-oracle concern is WAIVED — the date of birth identifies a
player and may be shown to other therapists. A name alone never blocks; a
name + date-of-birth twin is a warning on create (« Create anyway ») and a
refusal on an identity correction. What each criterion asserted before, and
now:

* IO-1 was « a name shared with a player the user can't read is refused
  with the generic ``ask a manager`` WHATEVER the date of birth, on four
  paths ». NOW: on create (app route, ``create_portal_patient``,
  ``create``) the RIGHT date gets the twin warning naming the team, a WRONG
  date is no identity refusal at all (only the deliberate invalid value
  fails); on a rename of their own player (write) the right date gets the
  plain twin refusal, a wrong one none.
* IO-2 was « a readable twin keeps ``Another player already has…`` on
  create ». NOW: the create gets the team-naming warning and succeeds with
  ``sc_identity_force_create`` (« Create anyway »).
* IO-3 was « a DOB-only correction sharing an unreadable player's name is
  refused generically whatever the date ». NOW: a name alone never blocks
  (only the invalid value fails); onto the exact twin it is the plain
  refusal.
* IO-4 (admin / backend) unchanged in spirit: the admin's create gets the
  twin warning (new text), another date is created; the unguarded backend
  creates.
* IO-5 unchanged (a relationship outside the list is a field error).
* IO-6 was « the check flags the unreadable namesake
  (``data-sc-twin-elsewhere``) whatever the date ». NOW: no such flag; the
  right date flags the exact twin (``data-sc-exact``), like the user's own
  players. The ``sc_1023_twin_elsewhere`` tour is replaced by
  test_identity_warning_1716's tours.
* IO-7 unchanged (« Add to team » of a namesake).
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common

TWIN_B = "A player with this name and date of birth already exists (PC Team B)."
TWIN_A = "A player with this name and date of birth already exists (PC Team A)."
EXACT = "Another player already has this name and date of birth."
RIGHT, WRONG = '2010-02-03', '2001-01-01'  # Élodie's date of birth, and not
BAD_STATUS = {'match_status': 'yes', 'practice_status': 'no'}
BAD_STATUS_MSG = "Invalid combination of match and practice status."


@tagged('post_install', '-at_install')
class TestIdentityOracle1023(PlayerAdd1655Common):

    def _error(self, func):
        with self.assertRaises(ValidationError) as caught:
            with self.env.cr.savepoint(), mute_logger('odoo.sql_db'):
                func()
        return str(caught.exception.args[0])

    def _create_xhr(self, **data):
        data.setdefault('csrf_token', self._csrf())
        data.setdefault('return_url', '/my/players')
        return self.url_open('/my/app/player/create', data=data, allow_redirects=False,
                             headers={'X-Requested-With': 'XMLHttpRequest'})

    def _elodie_vals(self, dob, **extra):
        return dict({'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': dob,
                     'team_ids': [Command.set([self.team_a.id])]}, **extra)

    # -- IO-1 (path 1) -----------------------------------------------------
    @mute_logger('odoo.http')
    def test_app_create_twin_warning_follows_the_dob(self):
        self._login_tp()
        resp = self._create_xhr(first_name='Élodie', last_name='Synthé-Côté', date_of_birth=RIGHT,
                                team_ids=str(self.team_a.id))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], TWIN_B)
        resp = self._create_xhr(first_name='Élodie', last_name='Synthé-Côté', date_of_birth=WRONG,
                                team_ids=str(self.team_a.id))
        self.assertEqual(resp.status_code, 200, resp.text[:200])
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(self.env['sports.patient'].search_count([('last_name', '=', 'Synthé-Côté')]), 2)

    # -- IO-1 (paths 2, 3) -------------------------------------------------
    def test_rpc_create_twin_warning_follows_the_dob(self):
        for user in (self.tp, self.coach):
            Patient = self.env['sports.patient'].with_user(user)
            for method in ('create_portal_patient', 'create'):
                right = self._error(lambda: getattr(Patient, method)(self._elodie_vals(RIGHT, **BAD_STATUS)))
                self.assertEqual(right, TWIN_B, (user.login, method))
                # Another date: no identity refusal — the create goes on to
                # its other checks (the invalid status pair, or a coach's
                # missing create rights on a path the app never uses).
                with self.assertRaises(Exception) as caught:
                    with self.env.cr.savepoint(), mute_logger('odoo.sql_db'):
                        getattr(Patient, method)(self._elodie_vals(WRONG, **BAD_STATUS))
                self.assertNotIn('already', str(caught.exception), (user.login, method))
        # Archived: still a twin.
        self.elodie.active = False
        error = self._error(lambda: self.env['sports.patient'].with_user(self.tp).create_portal_patient(
            self._elodie_vals(RIGHT)))
        self.assertEqual(error, TWIN_B)

    # -- IO-1 (path 4) -----------------------------------------------------
    def test_rpc_rename_own_player(self):
        player = self.player.with_user(self.tp).with_context(sc_identity_confirmed=True)
        right = self._error(lambda: player.write(dict(
            {'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': RIGHT}, **BAD_STATUS)))
        wrong = self._error(lambda: player.write(dict(
            {'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': WRONG}, **BAD_STATUS)))
        self.assertEqual(right, EXACT)
        self.assertEqual(wrong, BAD_STATUS_MSG)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.first_name, self.player.last_name), ('Pat', 'One'))
        player.write({'first_name': 'Patrick'})
        self.assertEqual(self.player.first_name, 'Patrick')

    # -- IO-2 --------------------------------------------------------------
    def test_readable_twin_warning_then_force(self):
        Patient = self.env['sports.patient'].with_user(self.tp)
        vals = {'first_name': ' pat ', 'last_name': 'ONE', 'team_ids': [Command.set([self.team_a.id])]}
        error = self._error(lambda: Patient.create_portal_patient(dict(vals, date_of_birth='2009-04-05')))
        self.assertEqual(error, TWIN_A)
        forced = Patient.with_context(sc_identity_force_create=True).create_portal_patient(
            dict(vals, date_of_birth='2009-04-05'))
        self.assertTrue(forced.exists())
        created = Patient.create_portal_patient(dict(vals, date_of_birth='2009-04-06'))
        self.assertTrue(created.exists())

    # -- IO-3 --------------------------------------------------------------
    def test_dob_only_correction_name_never_blocks(self):
        mine = self.env['sports.patient'].create({
            'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': '2012-01-01',
            'team_ids': [Command.set([self.team_a.id])]})
        for user in (self.tp, self.coach):
            player = mine.with_user(user).with_context(sc_identity_confirmed=True)
            self.assertEqual(self._error(lambda: player.write(dict({'date_of_birth': WRONG}, **BAD_STATUS))),
                             BAD_STATUS_MSG, user.login)
            self.assertEqual(self._error(lambda: player.write({'date_of_birth': RIGHT})), EXACT, user.login)
        self.assertEqual(mine.date_of_birth.isoformat(), '2012-01-01')
        mine.with_user(self.tp).write({'first_name': 'Élodie', 'position': 'Synthetic wing'})
        self.assertEqual(mine.position, 'Synthetic wing')

    # -- IO-4 --------------------------------------------------------------
    def test_admin_and_backend(self):
        admin = self.env(user=self.cadmin, context=dict(self.env.context, sc_identity_guard=True))
        error = self._error(lambda: admin['sports.patient'].create_portal_patient(
            self._elodie_vals(RIGHT, **BAD_STATUS)))
        self.assertEqual(error, TWIN_B)
        self.assertTrue(admin['sports.patient'].create_portal_patient(self._elodie_vals(WRONG)).exists())
        backend = self.env(user=self.itp)['sports.patient']
        self.assertTrue(backend.create_portal_patient(self._elodie_vals(RIGHT)).exists())

    # -- IO-5 --------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_bad_relationship_is_a_field_error(self):
        self._login_tp()
        resp = self._create_xhr(first_name='Nova', last_name='Synthetic', date_of_birth='2011-05-06',
                                team_ids=str(self.team_a.id), ec_name='Synthetic Parent',
                                ec_contact_type='bogus', ec_mobile='514 555 0131')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'ec_contact_type')
        self.assertFalse(self.env['sports.patient'].search([('first_name', '=', 'Nova')]))
        # Without the script: back to the panel, no 500.
        resp = self._create(first_name='Nova', last_name='Synthetic', date_of_birth='2011-05-06',
                            team_ids=str(self.team_a.id), ec_name='Synthetic Parent',
                            ec_contact_type='bogus', ec_mobile='514 555 0131')
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('add=1', resp.headers['Location'])

    # -- IO-6 --------------------------------------------------------------
    def test_check_flags_the_twin_by_dob(self):
        self._login_tp()
        _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob=RIGHT)
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        self.assertFalse(tree.xpath('//*[@data-sc-check-results]/@data-sc-twin-elsewhere'))
        for dob in (WRONG, ''):
            _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob=dob)
            self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'], dob)
        _resp, tree = self._check(first='elo', last='synthe', dob=RIGHT)
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])

    # -- IO-7 --------------------------------------------------------------
    def test_namesake_still_added_to_team(self):
        self._login_tp()
        resp = self.url_open('/my/team/%s/player/add' % self.team_a.id, data={
            'csrf_token': self._csrf(), 'existing_id': self.elodie.id, 'sc_inline': '1',
            'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': WRONG,
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn(self.team_a, self.elodie.team_ids)
