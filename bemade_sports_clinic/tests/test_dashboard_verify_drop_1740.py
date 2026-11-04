"""Task 1740 — dashboard « Blessures à vérifier »: the card leaves the list at
once after « Vérifier » (was: an empty shell, the pencil / chevron left).
Synthetic fixtures only (this repository is public).

Acceptance criteria:

* UC-1 Each injury line of « À faire » is a LIST read fragment
  (``sc.dashboard:todo:<row_scope>:list``, mode « list ») whose items are the
  injury cards (``sports.patient.injury:<id>:card``); the activity / player
  lines are not.
* UC-2 « Vérifier » answers refresh patterns that match the line and its
  count chip; the fresh render then lists the other injury only, count 1;
  the last one verified, the line and its count are gone (hidden on the
  page).
* UC-3 The player page carries no dashboard key: the injury card there is
  refreshed as before (its own fragments).
* UC-4 In a browser, phone 390 px: « Vérifier » on the dashboard drops the
  card without a reload, the count goes 2 → 1; the second one hides the line
  (static/tests/tours/sc_verify_drop_1740_tours.js).
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin

LIST_KEY = 'sc.dashboard:todo:dash-todo-verify:list'
COUNT_KEY = 'sc.dashboard:todo:dash-todo-verify'


class _Verify1740:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Injury = cls.env['sports.patient.injury']
        cls.inj_one = Injury.create({'patient_id': cls.yellow.id, 'diagnosis': 'Synthetic tweak one'})
        cls.inj_two = Injury.create({'patient_id': cls.red.id, 'diagnosis': 'Synthetic tweak two'})
        (cls.inj_one | cls.inj_two).with_context(mail_notrack=True).write({'stage': 'unverified'})
        # An overdue activity: an activity line next to the injury line.
        cls.env['mail.activity'].create({
            'res_model_id': cls.env['ir.model']._get('sports.patient').id, 'res_id': cls.red.id,
            'user_id': cls.tp.id, 'summary': 'Synthetic overdue 1740',
            'date_deadline': fields.Date.context_today(cls.tp) - timedelta(days=2)})


@tagged('post_install', '-at_install')
class TestVerifyDrop1740(_Verify1740, FragmentsMixin, Dashboard1624Common):

    def _verify(self, injury):
        resp = self.url_open('/my/injury/%s/verify' % injury.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        return resp.json()

    # -- UC-1 ---------------------------------------------------------------
    def test_injury_line_is_a_list_fragment(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        line = todo.xpath('.//details[@data-sc-todo="verify"]')[0]
        self.assertEqual(line.get('data-sc-fragment'), LIST_KEY)
        self.assertEqual(line.get('data-sc-fragment-mode'), 'list')
        self.assertEqual(sorted(line.xpath('.//*[@data-sc-fragment-item]/@data-sc-fragment-item')),
                         sorted('sports.patient.injury:%s:card' % i.id for i in (self.inj_one, self.inj_two)))
        overdue = todo.xpath('.//details[@data-sc-todo="activities_overdue"]')[0]
        self.assertIsNone(overdue.get('data-sc-fragment'))
        self.assertIsNone(overdue.get('data-sc-fragment-mode'))
        self.assertFragmentMatchesPage('/my/home', LIST_KEY)

    # -- UC-2 ---------------------------------------------------------------
    def test_verify_drops_the_card(self):
        self._login_tp()
        payload = self._verify(self.inj_one)
        self.assertEqual(self.inj_one.stage, 'active')
        self.assertRefreshes(payload, LIST_KEY)
        self.assertRefreshes(payload, COUNT_KEY)
        answer = self._fragments('/my/home', [LIST_KEY, COUNT_KEY])
        line = answer['fragments'][LIST_KEY]
        self.assertNotIn('sports.patient.injury:%s:card' % self.inj_one.id, line)
        self.assertIn('sports.patient.injury:%s:card' % self.inj_two.id, line)
        self.assertIn('>1<', answer['fragments'][COUNT_KEY].replace(' ', ''))
        # The last one: the line and its count are gone.
        self._verify(self.inj_two)
        answer = self._fragments('/my/home', [LIST_KEY, COUNT_KEY])
        self.assertEqual(sorted(answer['missing']), sorted([LIST_KEY, COUNT_KEY]))

    # -- UC-3 ---------------------------------------------------------------
    def test_player_page_has_no_dashboard_key(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % self.yellow.id)
        self.assertFalse([k for k in tree.xpath('//@data-sc-fragment') if k.startswith('sc.dashboard:')])
        self.assertTrue(tree.xpath('//*[@data-sc-fragment-item="sports.patient.injury:%s:card"]'
                                   % self.inj_one.id))


@tagged('post_install', '-at_install')
class TestVerifyDropTourPhone1740(_Verify1740, Dashboard1624Common):
    browser_size = '390x844'

    def test_verify_drop_tour(self):
        self.start_tour('/my/home', 'sc_1740_verify_drop', login='pc.tp@example.com')
        self.assertEqual((self.inj_one | self.inj_two).mapped('stage'), ['active', 'active'])
