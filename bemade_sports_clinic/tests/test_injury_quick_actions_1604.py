"""Task 1604 — quick « Vérifier » (one tap) and « Résoudre » (confirm +
resolution date) on the collapsed injury card row and on the injury page,
therapists only. Synthetic fixtures only (this repository is public).

Use case: a therapist sees an unverified injury in a player's list (or the
clinic dossier) and verifies it without opening the card and switching to
edit mode; an active one is resolved after confirming the resolution date.

Acceptance criteria:

* AC-1 Verify: ``POST /my/injury/<id>/verify`` (CSRF) by a therapist with
  access to an UNVERIFIED injury answers 200 like a save of ``stage``
  (``ok``, ``value`` « active », ``also``, ``refresh`` covering the card's
  summary and the player's fragments, ``saved_at``): the injury is active,
  the « Vérifier la blessure » To-Do is closed and « Injury verified by … »
  is logged.
* AC-2 Resolve: ``POST /my/injury/<id>/resolve`` with ``resolution_date``
  on an ACTIVE injury resolves it with THAT date (a past date is allowed;
  no date = today) and logs « Injury marked as resolved by … »; the answer
  carries ``also.resolution_date``. A future or malformed date is refused
  (400) and nothing is written.
* AC-3 Wrong stage: verify on a non-unverified injury, resolve on a
  non-active one -> 400, nothing changes.
* AC-4 Refusals: a coach, a plain portal user, a therapist without access
  to the injury's player -> 403, nothing changes.
* AC-5 Resolving the player's LAST active injury answers ``propose``
  (#1603 « last_resolved ») with the actual return = the chosen date;
  verifying an injury with a predicted date proposes Retour prévu.
* AC-6 Buttons: a therapist sees « Verify » on an unverified card's
  collapsed row, « Resolve » on an active one, nothing on a resolved one —
  in the card's ``<summary>`` (a separate control, so it refreshes with the
  summary fragment) on the player page and the clinic dossier, and in the
  injury page's header; the resolve sheet (date input, max = today) is on
  the page. A coach sees no button and no sheet.
* AC-8 fr_CA: « Vérifier », « Résoudre », the sheet (« Résoudre cette
  blessure ? », « Date de résolution », its error line) and the routes'
  messages render in French.
* AC-7 #1612 follow-up: ANY transition out of « unverified » closes the
  verification To-Do — including unverified -> resolved via the status
  selector (no « verified » message then).
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.patient_injury import VERIFY_INJURY_SUMMARY
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_clinic_dossier_inline_1590 import ClinicDossier1590Common

D = fields.Date.to_date


class QuickActionsMixin:

    def _quick(self, injury, action, **data):
        return self.url_open('/my/injury/%s/%s' % (injury.id, action), data={
            'csrf_token': self._csrf(), **data}, allow_redirects=False)

    @staticmethod
    def _summary(tree, injury):
        nodes = tree.xpath('//*[@data-sc-fragment="sports.patient.injury:%s:summary"]' % injury.id)
        return nodes[0] if nodes else None

    @staticmethod
    def _buttons(node, action=None):
        if node is None:
            return []
        if action:
            return node.xpath('.//button[@data-sc-injury-quick="%s"]' % action)
        return node.xpath('.//button[@data-sc-injury-quick]')


@tagged('post_install', '-at_install')
class TestInjuryQuickActions1604(QuickActionsMixin, FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Injury = env['sports.patient.injury']
        cls.injury.write({'diagnosis': 'Synthetic ankle'})
        cls.unverified = Injury.create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic strain',
            'predicted_resolution_date': '2030-03-01'})
        cls.unverified.with_context(mail_notrack=True).write({'stage': 'unverified'})
        cls.resolved = Injury.create({'patient_id': cls.player.id, 'diagnosis': 'Synthetic old'})
        cls.resolved.with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': '2029-01-01'})
        cls.foreign = Injury.create({'patient_id': cls.player_b.id, 'diagnosis': 'Synthetic other'})
        cls.foreign.with_context(mail_notrack=True).write({'stage': 'unverified'})
        cls.todo = env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id,
            'res_id': cls.player.id,
            'injury_id': cls.unverified.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': '[Injury: Synthetic strain] ' + VERIFY_INJURY_SUMMARY,
            'user_id': cls.tp.id,
            'date_deadline': fields.Date.today(),
        })

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def _open_todos(self, injury):
        return self.env['mail.activity'].search(
            injury._verify_activity_domain() + [('active', '=', True)])

    def _messages(self, injury, marker):
        injury.invalidate_recordset()
        return injury.sudo().message_ids.filtered(lambda m: marker in (m.body or ''))

    def _today(self):
        return fields.Date.context_today(self.injury)

    # -- AC-1 ------------------------------------------------------------
    def test_verify_one_tap(self):
        self._login_tp()
        resp = self._quick(self.unverified, 'verify')
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['value'], 'active')
        self.assertTrue(payload['display'] and payload['write_date'] and payload['saved_at'])
        self.assertEqual(payload['also']['stage']['value'], 'active')
        self.assertRefreshes(payload, 'sports.patient.injury:%s:summary' % self.unverified.id)
        self.assertRefreshes(payload, 'sports.patient:%s:injuries' % self.player.id)
        self.unverified.invalidate_recordset()
        self.assertEqual(self.unverified.stage, 'active')
        self.assertFalse(self._open_todos(self.unverified))
        self.assertEqual(len(self._messages(self.unverified, 'Injury verified by')), 1)

    # -- AC-2 ------------------------------------------------------------
    def test_resolve_with_a_chosen_date(self):
        self._login_tp()
        day = self._today() - timedelta(days=3)
        resp = self._quick(self.injury, 'resolve', resolution_date=fields.Date.to_string(day))
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload['value'], 'resolved')
        self.assertEqual(payload['also']['resolution_date']['value'], fields.Date.to_string(day))
        self.assertTrue(payload['also']['resolution_date']['display'])
        self.assertRefreshes(payload, 'sports.patient.injury:%s:read' % self.injury.id)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertEqual(self.injury.resolution_date, day)
        self.assertEqual(len(self._messages(self.injury, 'Injury marked as resolved by')), 1)

    def test_resolve_defaults_to_today(self):
        self._login_tp()
        resp = self._quick(self.injury, 'resolve')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.resolution_date, self._today())

    @mute_logger('odoo.http')
    def test_resolve_refuses_future_or_bad_date(self):
        self._login_tp()
        future = fields.Date.to_string(self._today() + timedelta(days=1))
        for value in (future, 'nope'):
            resp = self._quick(self.injury, 'resolve', resolution_date=value)
            self.assertEqual(resp.status_code, 400, value)
            self.assertTrue(resp.json().get('message'))
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'active')
        self.assertFalse(self.injury.resolution_date)

    # -- AC-3 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_wrong_stage_refused(self):
        self._login_tp()
        self.assertEqual(self._quick(self.injury, 'verify').status_code, 400)
        self.assertEqual(self._quick(self.resolved, 'verify').status_code, 400)
        self.assertEqual(self._quick(self.unverified, 'resolve').status_code, 400)
        self.assertEqual(self._quick(self.resolved, 'resolve').status_code, 400)
        self.env.invalidate_all()
        self.assertEqual(
            (self.injury.stage, self.unverified.stage, self.resolved.stage),
            ('active', 'unverified', 'resolved'))
        self.assertEqual(self.resolved.resolution_date, D('2029-01-01'))
        self.assertTrue(self.todo.active)

    # -- AC-4 ------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_refusals(self):
        for login in (self._login_coach, self._login_plain):
            login()
            self.assertEqual(self._quick(self.unverified, 'verify').status_code, 403)
            self.assertEqual(self._quick(self.injury, 'resolve').status_code, 403)
        self._login_tp()
        self.assertEqual(self._quick(self.foreign, 'verify').status_code, 403)
        self.env.invalidate_all()
        self.assertEqual(
            (self.injury.stage, self.unverified.stage, self.foreign.stage),
            ('active', 'unverified', 'unverified'))
        self.assertTrue(self.todo.active)

    # -- AC-5 ------------------------------------------------------------
    def test_last_active_resolved_chains_the_proposal(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self._login_tp()
        day = fields.Date.to_string(self._today() - timedelta(days=2))
        payload = self._quick(self.injury, 'resolve', resolution_date=day).json()
        proposal = payload['propose']
        self.assertEqual(proposal['kind'], 'last_resolved')
        items = {item['field']: item for item in proposal['items']}
        self.assertEqual(items['return_date']['proposed'], day)
        self.assertEqual(items['predicted_return_date']['proposed'], '')

    def test_verify_with_predicted_date_proposes_retour_prevu(self):
        self._login_tp()
        payload = self._quick(self.unverified, 'verify').json()
        self.assertEqual(payload['propose']['kind'], 'retour_prevu')
        self.assertEqual(payload['propose']['items'][0]['proposed'], '2030-03-01')

    # -- AC-6 ------------------------------------------------------------
    def test_buttons_on_the_collapsed_rows(self):
        self._login_tp()
        tree = self._page(self._url())
        self.assertEqual(len(self._buttons(self._summary(tree, self.unverified), 'verify')), 1)
        self.assertEqual(len(self._buttons(self._summary(tree, self.injury), 'resolve')), 1)
        self.assertEqual(self._buttons(self._summary(tree, self.unverified), 'resolve'), [])
        self.assertEqual(self._buttons(self._summary(tree, self.resolved)), [])
        [button] = self._buttons(self._summary(tree, self.injury), 'resolve')
        self.assertEqual(button.get('data-sc-injury-id'), str(self.injury.id))
        self.assertEqual(button.get('type'), 'button')
        sheet = tree.xpath('//dialog[@id="sc_injury_resolve_sheet"]')
        self.assertEqual(len(sheet), 1)
        [date_input] = sheet[0].xpath('.//input[@name="resolution_date"]')
        self.assertEqual(date_input.get('type'), 'date')
        self.assertEqual(date_input.get('max'), fields.Date.to_string(self._today()))
        # The summary fragment carries the button (it follows a verify).
        self.assertFragmentMatchesPage(self._url(), 'sports.patient.injury:%s:summary' % self.unverified.id)
        self._quick(self.unverified, 'verify')
        node = self._fragment(self._url(), 'sports.patient.injury:%s:summary' % self.unverified.id)
        self.assertEqual(len(self._buttons(node, 'resolve')), 1)
        self.assertEqual(self._buttons(node, 'verify'), [])

    def test_buttons_on_the_injury_page(self):
        # Task 1616: the injury page is the open card — its row (summary)
        # carries the button.
        self._login_tp()
        for injury, action in ((self.unverified, 'verify'), (self.injury, 'resolve')):
            tree = self._page('/my/injury/edit?injury_id=%s' % injury.id)
            card = tree.xpath('//details[@id="injury-%s"][@open]' % injury.id)
            self.assertEqual(len(card), 1, action)
            summary = card[0].xpath('./summary[@data-sc-fragment="sports.patient.injury:%s:summary"]' % injury.id)
            self.assertEqual(len(self._buttons(summary[0], action)), 1, action)
            self.assertEqual(len(tree.xpath('//dialog[@id="sc_injury_resolve_sheet"]')), 1)
        tree = self._page('/my/injury/edit?injury_id=%s' % self.resolved.id)
        card = tree.xpath('//details[@id="injury-%s"]' % self.resolved.id)
        self.assertEqual(self._buttons(card[0] if card else None), [])

    def test_coach_sees_no_button(self):
        self._login_coach()
        tree = self._page(self._url())
        self.assertEqual(tree.xpath('//button[@data-sc-injury-quick]'), [])
        self.assertEqual(tree.xpath('//dialog[@id="sc_injury_resolve_sheet"]'), [])
        tree = self._page('/my/injury/edit?injury_id=%s' % self.unverified.id)
        self.assertEqual(tree.xpath('//button[@data-sc-injury-quick]'), [])

    # -- AC-7 ------------------------------------------------------------
    def test_unverified_to_resolved_closes_the_todo(self):
        self._login_tp()
        resp = self._save(self.unverified, 'stage', 'resolved')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(self._open_todos(self.unverified))
        self.assertFalse(self._messages(self.unverified, 'Injury verified by'))

    def test_any_write_out_of_unverified_closes_the_todo(self):
        self.unverified.write({'stage': 'resolved'})
        self.assertFalse(self._open_todos(self.unverified))
        # A write that keeps it unverified leaves the To-Do alone.
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic other strain'})
        other.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.todo.write({'injury_id': other.id, 'active': True})
        other.write({'stage': 'unverified', 'diagnosis': 'Synthetic renamed'})
        self.assertTrue(self._open_todos(other))


@tagged('post_install', '-at_install')
class TestInjuryQuickActionsDossier1604(QuickActionsMixin, ClinicDossier1590Common):

    def test_buttons_in_the_clinic_dossier(self):
        self.injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        self.assertEqual(len(self._buttons(self._summary(tree, self.injury), 'verify')), 1)
        self.assertEqual(len(tree.xpath('//dialog[@id="sc_injury_resolve_sheet"]')), 1)


@tagged('post_install', '-at_install')
class TestInjuryQuickI18n1604(TestAppShellI18n1538):
    """fr_CA by render (website-aware: fr_CA on every website + the
    ``frontend_lang`` cookie) and in the routes' answers."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def test_buttons_and_sheet_in_french(self):
        self._login_tp()
        text = self._fr(self._url()).replace('&#39;', "'")
        for term in ('Résoudre', 'Résoudre cette blessure ?', 'Date de résolution',
                     "La blessure n'a pas pu être résolue."):
            self.assertIn(term, text, term)
        self.injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        tree = lxml_html.fromstring(self._fr(self._url()))
        [button] = tree.xpath('//button[@data-sc-injury-quick="verify"]')
        self.assertEqual(button.text_content().strip(), 'Vérifier')

    @mute_logger('odoo.http')
    def test_answers_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        future = fields.Date.to_string(fields.Date.context_today(self.injury) + timedelta(days=5))
        resp = self.url_open('/my/injury/%s/resolve' % self.injury.id, data={
            'csrf_token': self._csrf(), 'resolution_date': future})
        self.assertEqual(resp.json()['message'], 'La date de résolution ne peut pas être dans le futur.')
        resp = self.url_open('/my/injury/%s/verify' % self.injury.id, data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 400)
        resp = self.url_open('/my/injury/%s/resolve' % self.injury.id, data={'csrf_token': self._csrf()})
        self.assertEqual(resp.json()['message'], 'Blessure résolue.')
        resp = self.url_open('/my/injury/%s/resolve' % self.injury.id, data={'csrf_token': self._csrf()})
        self.assertEqual(resp.json()['message'], 'Seules les blessures actives peuvent être résolues.')
