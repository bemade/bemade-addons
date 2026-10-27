"""Task 1716 — adding a player: a name never blocks; name + date of birth is
a warning (add to the team, or « Create anyway »); an unlikely date of
birth asks for confirmation. Synthetic fixtures only.

Owner decisions 2026-10-26 (after discussion with MC): the 2026-10-23
security review's « date-of-birth oracle » concern is WAIVED — the date of
birth identifies a player and may be shown to other therapists.

Acceptance criteria:

* AC-1 Name-only namesake on another team: the create succeeds; the check
  lists it with its date of birth and team(s).
* AC-2 Exact twin (name + date of birth, any team, archived included): the
  check flags it (``data-sc-exact``) with « A player with this name and date
  of birth already exists (Team X). », « Add this player to the team » and
  « Create anyway »; the server refuses the create without
  ``force_create=1`` and creates it with.
* AC-3 Date of birth today / in the future / age < 3 or > 60: a warning in
  the check (« The date is correct »); the server refuses without
  ``dob_confirmed=1`` and creates after.
* AC-4 The suggestions of another team's players expose only name, date of
  birth and team names — no medical field (a coach gets no check at all:
  the route is therapists' / administrators', 403).
* AC-5 Browser (phone + laptop): exact twin → « Create » greyed with the
  reason → « Create anyway » → created; DOB today → « The date is correct »
  → created.
* AC-6 (review round 1, owner 2026-10-27): each override button has a
  hidden muted « ✓ Accepted by the user » next to it
  (``data-sc-check-accepted``) that replaces the button once clicked (the
  browser part in AC-5's tours).
"""
from datetime import date

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common


class Warning1716Common(PlayerAdd1655Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Élodie (PC Team B, out of the therapist's teams): medical data
        # that must never reach the suggestions.
        cls.env['sports.patient.injury'].create({
            'patient_id': cls.elodie.id, 'diagnosis': 'SYNTH-DIAG-1716'})

    def _exact(self, tree):
        return tree.xpath('//*[@data-sc-check-results]/@data-sc-exact')

    def _count(self, first, last):
        return self.env['sports.patient'].with_context(active_test=False).search_count(
            [('first_name', '=', first), ('last_name', '=', last)])


@tagged('post_install', '-at_install')
class TestIdentityWarning1716(Warning1716Common):

    # -- AC-1 ------------------------------------------------------------
    def test_name_only_namesake_never_blocks(self):
        self._login_tp()
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2012-01-01')
        self.assertEqual(self._exact(tree), ['0'])
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.elodie.id)
        # The typed date refines everyone now: another date → not listed.
        self.assertFalse(row)
        resp, tree = self._check(first='Élodie', last='Synthé-Côté')
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.elodie.id)[0]
        self.assertIn('02/03/2010', row.text_content())
        self.assertIn('PC Team B', row.text_content())
        resp = self._create(first_name='Élodie', last_name='Synthé-Côté', date_of_birth='2012-01-01',
                            team_ids=str(self.team_a.id))
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        self.assertEqual(self._count('Élodie', 'Synthé-Côté'), 2)

    # -- AC-2 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_exact_twin_is_a_warning_then_force(self):
        self._login_tp()
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2010-02-03', team_ids=self.team_a.id)
        self.assertEqual(self._exact(tree), ['1'])
        box = tree.xpath('//*[@data-sc-check-exact]')[0]
        self.assertIn('A player with this name and date of birth already exists (PC Team B).',
                      ' '.join(box.text_content().split()))
        self.assertTrue(box.xpath('.//button[@data-sc-player-add-force-btn]'))
        # AC-6: its « Accepted by the user » note, hidden until clicked.
        note = box.xpath('.//*[@data-sc-check-accepted="force"]')[0]
        self.assertEqual(note.get('hidden'), 'hidden')
        self.assertEqual(' '.join(note.text_content().split()), 'Accepted by the user')
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.elodie.id)[0]
        link = row.xpath('.//button[@data-sc-action="player.link"]')[0]
        self.assertEqual(' '.join(link.text_content().split()), 'Add this player to the team')
        # Out of the therapist's teams: no « Open ».
        self.assertFalse(row.xpath('.//a[@data-sc-check-open]'))
        self.assertNotIn('ask a manager', resp.text)
        data = dict(first_name='Élodie', last_name='Synthé-Côté', date_of_birth='2010-02-03',
                    team_ids=str(self.team_a.id))
        resp = self.url_open('/my/app/player/create', data=dict(data, csrf_token=self._csrf()),
                             headers={'X-Requested-With': 'XMLHttpRequest'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists (PC Team B)', resp.json()['message'])
        self.assertEqual(self._count('Élodie', 'Synthé-Côté'), 1)
        resp = self._create(force_create='1', **data)
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        self.assertEqual(self._count('Élodie', 'Synthé-Côté'), 2)

    def test_readable_twin_offers_open(self):
        self._login_tp()
        resp, tree = self._check(first='Pat', last='One', dob='2009-04-05')
        self.assertEqual(self._exact(tree), ['1'])
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.player.id)[0]
        self.assertTrue(row.xpath('.//a[@data-sc-check-open]'))

    # -- AC-3 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_unlikely_dob_needs_confirmation(self):
        self._login_tp()
        today = date.today()
        for dob, word in ((today, 'today'), (date(today.year + 1, 1, 1), 'future'),
                          (date(today.year - 1, 1, 1), 'age'), (date(today.year - 70, 1, 1), 'age')):
            resp, tree = self._check(first='Newsyn', last='Dobcheck', dob=dob.isoformat())
            self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-dob-warn'), ['1'], dob)
            self.assertIn(word, tree.xpath('//*[@data-sc-check-dob-warning]')[0].text_content(), dob)
        resp, tree = self._check(first='Newsyn', last='Dobcheck', dob='2012-06-01')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-dob-warn'), ['0'])
        data = dict(first_name='Newsyn', last_name='Dobcheck', date_of_birth=today.isoformat(),
                    team_ids=str(self.team_a.id))
        resp = self.url_open('/my/app/player/create', data=dict(data, csrf_token=self._csrf()),
                             headers={'X-Requested-With': 'XMLHttpRequest'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'date_of_birth')
        self.assertFalse(self._count('Newsyn', 'Dobcheck'))
        resp = self._create(dob_confirmed='1', **data)
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        self.assertEqual(self._count('Newsyn', 'Dobcheck'), 1)

    # -- AC-4 ------------------------------------------------------------
    def test_suggestions_expose_no_medical_field(self):
        self._login_tp()
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2010-02-03')
        self.assertNotIn('SYNTH-DIAG-1716', resp.text)
        row = tree.xpath('//li[@data-sc-check-player="%s"]' % self.elodie.id)[0]
        texts = [' '.join(n.text_content().split()) for n in row.xpath('.//span[contains(@class, "o_sc_row_subtitle")]')]
        self.assertEqual(len(texts), 2, texts)  # team(s), date of birth
        self._login_coach()
        resp, _tree = self._check(first='Élodie', last='Synthé-Côté')
        self.assertEqual(resp.status_code, 403)


class _Tours1716:

    def test_twin_create_anyway(self):
        self.start_tour('/my/players?add=1', 'sc_1716_twin_create_anyway', login='pc.tp@example.com')
        self.assertEqual(self._count('Élodie', 'Synthé-Côté'), 2)

    def test_dob_today_confirm(self):
        self.start_tour('/my/players?add=1', 'sc_1716_dob_today', login='pc.tp@example.com')
        self.assertEqual(self._count('Todaysyn', 'Dobtour'), 1)


@tagged('post_install', '-at_install')
class TestIdentityWarningPhone1716(_Tours1716, Warning1716Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestIdentityWarningLaptop1716(_Tours1716, Warning1716Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
