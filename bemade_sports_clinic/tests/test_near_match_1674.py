"""Task 1674 — near-match suggestions in every player search + the backend
« Possible duplicates » list. Synthetic names only.

Acceptance criteria:

* AC-1 Matcher (models/sc_name_match.py): accents, a missing / extra /
  substituted letter, a transposition, swapped first / last, a compound
  name (one part, particles optional), ph/f, double letters, silent final
  letters are NEAR; genuinely different names and short names are not.
* AC-2 Add-player check: near matches come after the exact / prefix ones,
  under « Similar players », with the same actions; « Create » stays
  enabled with only near matches (``data-sc-near``); S2 kept — an
  out-of-scope near match's answer is the same whatever date is typed.
* AC-3 Header search and the Joueurs list find a typo'd name in their
  « Close results » group, with the same scope / lock rules.
* AC-4 « Possible duplicates »: « Find duplicates » lists the synthetic
  pairs (same-DOB first), « Not a duplicate » is remembered across a new
  search, « Merge… » opens the Merge Players wizard with the pair.
* AC-5 Speed: ~1,200 synthetic players, a search < 150 ms, the duplicate
  scan < 2 s.
"""
import random
import string
import time

from lxml import html as lxml_html

from odoo import Command
from odoo.service.model import call_kw
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models import sc_name_match as m
from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common


def _grade(first, last, cand_first, cand_last):
    return m.grade(m.NameForm(first), m.NameForm(last), m.NameForm(cand_first), m.NameForm(cand_last))


@tagged('post_install', '-at_install')
class TestNameMatcher1674(TransactionCase):

    def test_exact_after_normalisation(self):
        self.assertEqual(_grade('Elodie', 'Synthe Cote', 'Élodie', 'Synthé-Côté'), m.EXACT)
        self.assertEqual(_grade('Jean', 'St-Pierre', 'Jean', 'Saint Pierre'), m.EXACT)
        self.assertEqual(_grade('Zoe', "D'Synthe", 'Zoé', 'D Synthe'), m.EXACT)
        # Particles optional.
        self.assertEqual(_grade('Clara', 'Fontaine', 'Clara', 'de la Fontaine'), m.EXACT)

    def test_prefix_as_today(self):
        self.assertEqual(_grade('Ma', 'Synth', 'Marion', 'Synthetica'), m.PREFIX)

    def test_near(self):
        cases = [
            ('Jonathan', 'Synthwell', 'Jonahtan', 'Synthwell'),     # transposition
            ('Annabelle', 'Synthard', 'Anabelle', 'Synthard'),      # missing letter
            ('Mathieu', 'Synthevre', 'Matthieu', 'Synthevre'),      # extra / double letter
            ('Marion', 'Synthier', 'Marion', 'Synthyer'),           # substitution
            ('Synthwell', 'Jonathan', 'Jonathan', 'Synthwell'),     # swapped
            ('Philippe', 'Synthault', 'Filippe', 'Synthaut'),       # ph/f + silent final
        ]
        for case in cases:
            self.assertEqual(_grade(*case), m.NEAR, case)

    def test_compound_names(self):
        # One part of a compound name: typed as a prefix already matches.
        self.assertEqual(_grade('Clara', 'Cote', 'Clara', 'Synthe-Cote'), m.PREFIX)
        a, b = m.NameForm('Cote'), m.NameForm('Synthe-Cote')
        self.assertTrue(m.name_near(a, b) and m.name_near(b, a))
        # Two different compounds sharing a part are not the same name.
        self.assertFalse(m.name_near(m.NameForm('Synthe-Roy'), m.NameForm('Synthe-Gagnon')))

    def test_negatives(self):
        cases = [
            ('Paul', 'Synthwell', 'Pierre', 'Synthwell'),           # another first name
            ('Anne', 'Lee', 'Anne', 'Lea'),                         # short name: no typo budget
            ('Marc', 'Roy', 'Luc', 'Roy'),
            ('Jonathan', 'Synthwell', 'Jonathan', 'Brightmore'),    # another family
        ]
        for case in cases:
            self.assertIsNone(_grade(*case), case)

    def test_words(self):
        index = m.NameIndex([(1, 'Jonathan', 'Synthwell'), (2, 'Paul', 'Other')])
        self.assertEqual(index.match_words(['jonahtan']), [(1, m.NEAR)])
        self.assertEqual(index.match_words(['jon']), [(1, m.PREFIX)])

    def test_duplicate_pairs(self):
        pairs = m.duplicate_pairs([
            (1, 'Jonathan', 'Synthwell', '2010-01-01'),
            (2, 'Jonahtan', 'Synthwell', '2010-01-01'),
            (3, 'Synthwell', 'Jonathan', None),
            (4, 'Élodie', 'Synthé', None),
            (5, 'Elodie', 'Synthe', None),
            (6, 'Paul', 'Other', None),
        ])
        found = {(a, b): (kind, same) for a, b, kind, same in pairs}
        self.assertEqual(found[(1, 2)], ('near', True))
        self.assertEqual(found[(1, 3)], ('swapped', False))
        self.assertEqual(found[(4, 5)], ('exact', False))
        self.assertFalse([pair for pair in found if 6 in pair])
        self.assertEqual(pairs[0][:2], (1, 2), 'same date of birth first')

    # -- AC-5 --------------------------------------------------------------
    def test_speed_on_1200_players(self):
        rng = random.Random(1674)
        syll = ['ma', 'ri', 'jo', 'na', 'than', 'el', 'lo', 'die', 'syn', 'the', 'well', 'bou', 'chard',
                'tre', 'blay', 'ga', 'gnon', 'ro', 'cote', 'pier', 're', 'lu', 'cas', 'fon', 'taine']

        def name():
            return ''.join(rng.choice(syll) for _i in range(rng.randint(2, 3))).title()
        rows = [(i, name(), name()) for i in range(1200)]
        start = time.perf_counter()
        index = m.NameIndex(rows)
        for first, last in (('Jonathan', 'Synthwell'), ('Marie', 'Tremblay'), ('Lucas', 'Gagnon')):
            index.match(first, last)
        per_search = (time.perf_counter() - start) / 3
        self.assertLess(per_search, 0.150, 'a search on 1,200 players took %.0f ms' % (per_search * 1000))
        start = time.perf_counter()
        m.duplicate_pairs([(i, f, l, None) for i, f, l in rows])
        self.assertLess(time.perf_counter() - start, 2.0)


@tagged('post_install', '-at_install')
class TestNearMatchApp1674(PlayerAdd1655Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.jonathan = env['sports.patient'].create({
            'first_name': 'Jonathan', 'last_name': 'Synthwell', 'date_of_birth': '2011-02-03'})
        cls.jonathan.team_ids = [Command.set([cls.team_a.id])]
        cls.jonathan_twin = env['sports.patient'].create({
            'first_name': 'Jonahtan', 'last_name': 'Synthwell', 'date_of_birth': '2011-02-03'})
        cls.jonathan_twin.team_ids = [Command.set([cls.team_a.id])]

    def _rows(self, tree, group):
        return [int(li.get('data-sc-check-player'))
                for li in tree.xpath('//ul[@data-sc-check-group="%s"]/li' % group)]

    # -- AC-2 --------------------------------------------------------------
    def test_check_lists_similar_players(self):
        self._login_tp()
        _resp, tree = self._check(first='Jonathn', last='Synthwel')
        self.assertIn(self.jonathan.id, self._rows(tree, 'near'))
        self.assertTrue(tree.xpath('//*[@data-sc-check-near]'))
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-near'), ['1'])
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])
        # Exact / prefix first, near after.
        _resp, tree = self._check(first='Jonathan', last='Synthwell')
        self.assertIn(self.jonathan.id, self._rows(tree, 'match'))
        self.assertIn(self.jonathan_twin.id, self._rows(tree, 'near'))

    def test_check_near_s2_out_of_scope(self):
        self._login_tp()
        answers = []
        for dob in ('2010-02-03', '2001-01-01', ''):
            resp, tree = self._check(first='Elodei', last='Synthe-Cote', dob=dob)
            self.assertIn(self.elodie.id, self._rows(tree, 'near'), dob)
            answers.append(resp.text)
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[0], answers[2])

    # -- AC-3 --------------------------------------------------------------
    def test_header_search_close_results(self):
        self._login_tp()
        resp = self.url_open('/my/app/search?q=jonahtan')
        tree = lxml_html.fromstring(resp.text)
        near = tree.xpath('//*[@data-sc-search-group="players_near"]//li/@data-sc-search-player')
        exact = tree.xpath('//*[@data-sc-search-group="players"]//li/@data-sc-search-player')
        self.assertIn(str(self.jonathan_twin.id), exact)
        self.assertIn(str(self.jonathan.id), near)

    def test_players_list_close_results(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/players?first_name=Jonathn&last_name=Synthwell')
        near = tree.xpath('//*[@data-sc-section="players.near"]//li/@data-sc-near-player')
        self.assertIn(str(self.jonathan.id), near)

    # -- AC-4 --------------------------------------------------------------
    def test_possible_duplicates(self):
        Dup = self.env['sports.patient.duplicate']
        action = Dup.action_find_duplicates()
        self.assertEqual(action['res_model'], 'sports.patient.duplicate')
        pair = Dup.search([('patient_a_id', '=', self.jonathan.id), ('patient_b_id', '=', self.jonathan_twin.id)])
        self.assertEqual((pair.kind, pair.same_dob), ('near', True))
        merge = pair.action_merge()
        self.assertEqual(merge['res_model'], 'sports.patient.merge.wizard')
        self.assertEqual(sorted(merge['context']['active_ids']), sorted([self.jonathan.id, self.jonathan_twin.id]))
        wizard = self.env['sports.patient.merge.wizard'].with_context(**merge['context']).new({})
        self.assertEqual(set(wizard.patient_ids.ids), {self.jonathan.id, self.jonathan_twin.id})
        pair.action_dismiss()
        Dup.action_find_duplicates()
        pairs = Dup.search([('patient_a_id', '=', self.jonathan.id), ('patient_b_id', '=', self.jonathan_twin.id)])
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs.dismissed)
        self.assertFalse(Dup.search([('dismissed', '=', False), ('patient_a_id', '=', self.jonathan.id),
                                     ('patient_b_id', '=', self.jonathan_twin.id)]))

    def test_find_duplicates_from_list_header(self):
        """Review 2026-10-25: the list header's « Find duplicates » button
        (display="always") goes through call_button with the selection as the
        first argument — an empty list when nothing is ticked, the ticked rows
        otherwise. Both must run the scan and return the list action (it
        crashed: « takes 1 positional argument but 2 were given »)."""
        Dup = self.env['sports.patient.duplicate']
        action = call_kw(Dup, 'action_find_duplicates', [[]], {})
        self.assertEqual(action['res_model'], 'sports.patient.duplicate')
        pair = Dup.search([('patient_a_id', '=', self.jonathan.id), ('patient_b_id', '=', self.jonathan_twin.id)])
        self.assertEqual(len(pair), 1)
        # With a ticked row (which the rescan itself replaces).
        action = call_kw(Dup, 'action_find_duplicates', [pair.ids], {})
        self.assertEqual(action['res_model'], 'sports.patient.duplicate')
        self.assertEqual(len(Dup.search([('patient_a_id', '=', self.jonathan.id),
                                         ('patient_b_id', '=', self.jonathan_twin.id)])), 1)


@tagged('post_install', '-at_install')
class TestNearMatchTour1674(PlayerAdd1655Common):
    browser_size = '390x844'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        jonathan = cls.env['sports.patient'].create({
            'first_name': 'Jonathan', 'last_name': 'Synthwell', 'date_of_birth': '2011-02-03'})
        jonathan.team_ids = [Command.set([cls.team_a.id])]

    def test_near_check_tour(self):
        self._switch(True)
        self.start_tour('/my/players?add=1', 'sc_1674_near_check', login='pc.tp@example.com')
