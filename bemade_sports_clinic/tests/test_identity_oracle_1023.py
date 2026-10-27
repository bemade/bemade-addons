"""Security review 2026-10-23: the identity duplicate guard is not a
date-of-birth oracle (19.0.1.107.1). Synthetic fixtures only.

The guard used to refuse an exact name + date-of-birth twin BEFORE the other
validations: adding a value sure to fail later, a right date of birth got
« duplicate », a wrong one the other error — a therapist (or a coach) could
confirm another team's player's date of birth by trial.

Acceptance criteria:

* IO-1 For a guarded user who is not a clinic administrator, a name shared
  with a player they can't read (another team's, archived included) is
  refused with the generic « A player with this identity already exists —
  ask a manager. », whatever the date of birth typed — the right one and a
  wrong one give the same error — on the four paths:
  1. ``POST /my/app/player/create`` (with an invalid relationship);
  2. RPC ``create_portal_patient`` (with an invalid status pair);
  3. RPC ``sports.patient.create`` (with an invalid status pair);
  4. RPC ``write`` on their own player (rename), identity confirmed (with an
     invalid status pair).
* IO-2 An exact twin the user CAN read keeps the exact « Another player
  already has this name and date of birth. »; the same name with another
  date of birth is created.
* IO-3 A date-of-birth-only correction of their own player that shares the
  name of a player they can't read gets the same generic refusal whatever the
  date (therapist and coach); a save that changes no identity field is not
  refused.
* IO-4 A clinic administrator (app flag) and an unguarded backend user keep
  the previous behaviour: the exact twin refusal, a namesake with another
  date of birth is created.
* IO-5 A relationship outside the list is a field error in the panel (400),
  never a 500.
* IO-6 The existence check flags the same-name player the user can't read
  (``data-sc-twin-elsewhere``) whatever the date, never for a prefix; the
  panel greys « Create » with the generic line (tour, phone).
* IO-7 A same-name player the user can't read can still be added to the
  team through « Add to team » (the team page's link route).
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common

GENERIC = "A player with this identity already exists — ask a manager."
EXACT = "Another player already has this name and date of birth."
RIGHT, WRONG = '2010-02-03', '2001-01-01'  # Élodie's date of birth, and not
BAD_STATUS = {'match_status': 'yes', 'practice_status': 'no'}


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
    def test_app_create_same_answer_whatever_the_dob(self):
        self._login_tp()
        for ec_type, message in (('bogus', "Please choose a relationship from the list."), ('mother', GENERIC)):
            answers = []
            for dob in (RIGHT, WRONG):
                resp = self._create_xhr(first_name='Élodie', last_name='Synthé-Côté', date_of_birth=dob,
                                        team_ids=str(self.team_a.id), ec_name='Synthetic Parent',
                                        ec_contact_type=ec_type, ec_mobile='514 555 0131')
                answers.append((resp.status_code, resp.json()))
            self.assertEqual(answers[0], answers[1], 'the right and a wrong date give the same answer')
            self.assertEqual(answers[0][0], 400)
            self.assertEqual(answers[0][1]['message'], message)
        self.assertEqual(self.env['sports.patient'].search_count([('last_name', '=', 'Synthé-Côté')]), 1)

    # -- IO-1 (paths 2, 3) -------------------------------------------------
    def test_rpc_create_same_answer_whatever_the_dob(self):
        for user in (self.tp, self.coach):
            Patient = self.env['sports.patient'].with_user(user)
            for method in ('create_portal_patient', 'create'):
                errors = [self._error(lambda dob=dob: getattr(Patient, method)(
                    self._elodie_vals(dob, **BAD_STATUS))) for dob in (RIGHT, WRONG)]
                self.assertEqual(errors, [GENERIC, GENERIC], (user.login, method))
        # Archived: the same.
        self.elodie.active = False
        error = self._error(lambda: self.env['sports.patient'].with_user(self.tp).create_portal_patient(
            self._elodie_vals(WRONG)))
        self.assertEqual(error, GENERIC)

    # -- IO-1 (path 4) -----------------------------------------------------
    def test_rpc_rename_own_player_same_answer_whatever_the_dob(self):
        player = self.player.with_user(self.tp).with_context(sc_identity_confirmed=True)
        errors = [self._error(lambda dob=dob: player.write(dict(
            {'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': dob}, **BAD_STATUS)))
            for dob in (RIGHT, WRONG)]
        self.assertEqual(errors, [GENERIC, GENERIC])
        self.player.invalidate_recordset()
        self.assertEqual((self.player.first_name, self.player.last_name), ('Pat', 'One'))
        # The #1600 rename of their own player to a free name still works.
        player.write({'first_name': 'Patrick'})
        self.assertEqual(self.player.first_name, 'Patrick')

    # -- IO-2 --------------------------------------------------------------
    def test_readable_twin_keeps_the_exact_refusal(self):
        Patient = self.env['sports.patient'].with_user(self.tp)
        vals = {'first_name': ' pat ', 'last_name': 'ONE', 'team_ids': [Command.set([self.team_a.id])]}
        error = self._error(lambda: Patient.create_portal_patient(dict(vals, date_of_birth='2009-04-05')))
        self.assertEqual(error, EXACT)
        created = Patient.create_portal_patient(dict(vals, date_of_birth='2009-04-06'))
        self.assertTrue(created.exists())

    # -- IO-3 --------------------------------------------------------------
    def test_dob_only_correction_same_answer_whatever_the_dob(self):
        # Their own player legitimately shares Élodie's name (set by a manager).
        mine = self.env['sports.patient'].create({
            'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': '2012-01-01',
            'team_ids': [Command.set([self.team_a.id])]})
        for user in (self.tp, self.coach):
            player = mine.with_user(user).with_context(sc_identity_confirmed=True)
            errors = [self._error(lambda dob=dob: player.write(dict({'date_of_birth': dob}, **BAD_STATUS)))
                      for dob in (RIGHT, WRONG)]
            self.assertEqual(errors, [GENERIC, GENERIC], user.login)
        self.assertEqual(mine.date_of_birth.isoformat(), '2012-01-01')
        # A save that changes no identity field is not refused.
        mine.with_user(self.tp).write({'first_name': 'Élodie', 'position': 'Synthetic wing'})
        self.assertEqual(mine.position, 'Synthetic wing')

    # -- IO-4 --------------------------------------------------------------
    def test_admin_and_backend_unchanged(self):
        admin = self.env(user=self.cadmin, context=dict(self.env.context, sc_identity_guard=True))
        error = self._error(lambda: admin['sports.patient'].create_portal_patient(
            self._elodie_vals(RIGHT, **BAD_STATUS)))
        self.assertEqual(error, EXACT)
        self.assertTrue(admin['sports.patient'].create_portal_patient(self._elodie_vals(WRONG)).exists())
        # The backend (an internal therapist, no app flag) is not guarded.
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
    def test_check_flags_the_unreadable_namesake(self):
        self._login_tp()
        for dob in (RIGHT, WRONG, ''):
            _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob=dob)
            self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-twin-elsewhere'), ['1'], dob)
        _resp, tree = self._check(first='elo', last='synthe', dob=RIGHT)
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-twin-elsewhere'), ['0'])
        _resp, tree = self._check(first='Pat', last='One')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-twin-elsewhere'), ['0'])
        self._login_cadmin()
        _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob=WRONG)
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-twin-elsewhere'), ['0'])

    def test_create_greyed_tour(self):
        self.browser_size = '390x844'
        self.start_tour('/my/players?add=1', 'sc_1023_twin_elsewhere', login='pc.tp@example.com')
        self.assertFalse(self.env['sports.patient'].search_count(
            [('first_name', '=', 'Élodie'), ('id', '!=', self.elodie.id)]))

    # -- IO-7 --------------------------------------------------------------
    def test_namesake_still_added_to_team(self):
        self._login_tp()
        resp = self.url_open('/my/team/%s/player/add' % self.team_a.id, data={
            'csrf_token': self._csrf(), 'existing_id': self.elodie.id, 'sc_inline': '1',
            'first_name': 'Élodie', 'last_name': 'Synthé-Côté', 'date_of_birth': WRONG,
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn(self.team_a, self.elodie.team_ids)
