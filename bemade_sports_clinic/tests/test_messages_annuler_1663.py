"""Task 1663 — app messages and « Annuler » consistency. Synthetic fixtures.

Acceptance criteria covered here (fr_CA renders, website-aware):

* AC-1 Player undo-create: success shows the toast « Création du joueur
  annulée. » on the page the user goes back to; a refused undo (past the 2
  minutes) lands on the player page with « Ce joueur ne peut plus être
  annulé ; retirez-le ou archivez-le depuis sa fiche. » — not the injury
  text.
* AC-2 Team announcement: the archive is instant; the team page then offers
  « Annonce archivée — Annuler »; the restore puts the same text and deadline
  back and the history reads « Archivée » then « Restaurée ». Refused for a
  coach, for another therapist, after the window, and when the announcement
  changed meanwhile.
* AC-3 Activities: the delete action reads « Supprimer » (row, detail page),
  its confirm « Supprimer cette activité ? » / « Oui, supprimer », the toast
  « Activité supprimée. »; no « Annuler l'activité » left in the app.
* AC-4 (tours, sc_messages_annuler_1663_tours.js) archive → toast « Undo »
  → the announcement is back; an activity's « Delete » → confirm → gone.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common


class Messages1663Common(PlayerAdd1655Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC TP Two', 'login': 'pc.tp2@example.com', 'password': 'pc-tp2',
            'group_ids': [Command.set([portal, tp_g])]})
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist'})

    def _french(self):
        for user in (self.tp, self.tp2, self.coach):
            user.sudo().lang = 'fr_CA'
        self.opener.cookies.set('frontend_lang', 'fr_CA')

    def _page(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'"), lxml_html.fromstring(resp.text)

    def _post_announcement(self, text='Synthetic bus leaves at 7', deadline='2099-01-31'):
        self.team_a.with_user(self.tp).write({
            'announcement': text, 'announcement_deadline': deadline})

    def _archive(self):
        return self.url_open('/my/team/%s/announcement/dismiss' % self.team_a.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)

    def _restore(self):
        return self.url_open('/my/team/%s/announcement/restore' % self.team_a.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestMessagesAnnuler1663(Messages1663Common):

    # -- AC-1 -------------------------------------------------------------
    def test_player_undo_success_toast(self):
        self._french()
        self._login_tp()
        self._create(first_name='Undo', last_name='Synthetic', date_of_birth='2011-05-09',
                     team_ids=str(self.team_a.id))
        player = self.env['sports.patient'].search([('first_name', '=', 'Undo'), ('last_name', '=', 'Synthetic')])
        resp = self.url_open('/my/player/%s/undo-create' % player.id,
                             data={'csrf_token': self._csrf(), 'return_url': '/my/players'},
                             allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertNotIn('success=player_undone', resp.headers['Location'])
        self.assertFalse(player.exists())
        _text, tree = self._page('/my/players')
        self.assertEqual(tree.xpath('//*[contains(@class, "o_sc_toast")]/@data-sc-notify'),
                         ['Création du joueur annulée.'])

    def test_player_undo_refused_message(self):
        self._french()
        self._login_tp()
        self._create(first_name='Late', last_name='Synthetic', date_of_birth='2011-05-10',
                     team_ids=str(self.team_a.id))
        player = self.env['sports.patient'].search([('first_name', '=', 'Late'), ('last_name', '=', 'Synthetic')])
        self.env.cr.execute("UPDATE sports_patient SET create_date = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(minutes=5), player.id))
        self.env.invalidate_all()
        resp = self.url_open('/my/player/%s/undo-create' % player.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        location = resp.headers['Location']
        self.assertIn('error=player_undo_expired', location)
        self.assertTrue(player.exists())
        text, _tree = self._page(location)
        self.assertIn('Ce joueur ne peut plus être annulé ; retirez-le ou archivez-le depuis sa fiche.', text)
        self.assertNotIn('Cette blessure ne peut plus être annulée', text)

    # -- AC-2 -------------------------------------------------------------
    def test_announcement_archive_then_restore(self):
        self._french()
        self._post_announcement()
        self._login_tp()
        resp = self._archive()
        self.assertIn('announcement_archived=1', resp.headers['Location'])
        self.assertFalse(self.team_a.announcement)
        _text, tree = self._page(resp.headers['Location'])
        form = tree.xpath('//form[@data-sc-form="announcement.undo"]')
        self.assertEqual(len(form), 1)
        # (website installed, CI: the form action carries the /fr prefix)
        self.assertTrue(form[0].get('action').endswith('/my/team/%s/announcement/restore' % self.team_a.id),
                        form[0].get('action'))
        self.assertEqual(form[0].get('data-sc-toast-message'), 'Annonce archivée')
        self.assertEqual(form[0].get('data-sc-toast-action'), 'Annuler')
        # A plain reload (no ?announcement_archived) offers nothing.
        _text, tree = self._page('/my/team?team_id=%s' % self.team_a.id)
        self.assertFalse(tree.xpath('//form[@data-sc-form="announcement.undo"]'))
        resp = self._restore()
        self.assertIn(resp.status_code, (302, 303))
        self.env.invalidate_all()
        self.assertEqual(self.team_a.announcement, 'Synthetic bus leaves at 7')
        self.assertEqual(fields.Date.to_string(self.team_a.announcement_deadline), '2099-01-31')
        self.assertEqual(self.team_a.announcement_author_id, self.tp)
        actions = self.team_a.sudo().note_history_ids.sorted('id').mapped('action')
        self.assertEqual(actions[-2:], ['dismiss', 'restore'])
        text, _tree = self._page('/my/team/%s/announcement/history' % self.team_a.id)
        self.assertIn('Restaurée', text)
        self.assertIn('Archivée', text)
        # Only once.
        self._restore()
        self.assertEqual(self.team_a.sudo().note_history_ids.sorted('id').mapped('action')[-1], 'restore')

    def test_restore_refused_for_coach(self):
        self._post_announcement()
        self._login_tp()
        self._archive()
        self._login_coach()
        self._restore()
        self.env.invalidate_all()
        self.assertFalse(self.team_a.announcement)

    def test_restore_refused_for_another_therapist(self):
        self._french()
        self._post_announcement()
        self._login_tp()
        self._archive()
        self.authenticate('pc.tp2@example.com', 'pc-tp2')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self._restore()
        self.env.invalidate_all()
        self.assertFalse(self.team_a.announcement)
        _text, tree = self._page(resp.headers['Location'])
        self.assertEqual(tree.xpath('//*[contains(@class, "o_sc_toast")]/@data-sc-notify'),
                         ['Cette annonce ne peut plus être restaurée.'])

    def test_restore_refused_after_window_or_change(self):
        self._post_announcement()
        self._login_tp()
        self._archive()
        history = self.env['sports.team.note.history'].sudo().search(
            [('team_id', '=', self.team_a.id)], order='id desc', limit=1)
        self.env.cr.execute("UPDATE sports_team_note_history SET note_datetime = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(minutes=2), history.id))
        self.env.invalidate_all()
        self._restore()
        self.env.invalidate_all()
        self.assertFalse(self.team_a.announcement)
        # Within the window, but a new announcement was posted meanwhile.
        self._post_announcement('Synthetic first')
        self._archive()
        self._post_announcement('Synthetic newer')
        self._restore()
        self.env.invalidate_all()
        self.assertEqual(self.team_a.announcement, 'Synthetic newer')

    # -- AC-3 -------------------------------------------------------------
    def test_activity_delete_wording(self):
        self._french()
        self._login_tp()
        text, tree = self._page('/my/activities')
        sheet = tree.xpath('//dialog[@id="sc_activity_cancel_sheet"]')[0]
        sheet_text = ' '.join(sheet.text_content().split())
        self.assertIn("Supprimer l'activité", sheet_text)
        self.assertIn('Supprimer cette activité ?', sheet_text)
        self.assertEqual(sheet.xpath('.//button[@type="submit"]')[0].text_content().strip(), 'Oui, supprimer')
        buttons = tree.xpath('//button[@data-sc-action="activity.cancel"]')
        self.assertTrue(buttons)
        for button in buttons:
            self.assertEqual(' '.join(button.text_content().split()), 'Supprimer')
        self.assertNotIn("Annuler l'activité", text)
        _text, tree = self._page('/my/activity/%s' % self.act_player.id)
        detail = tree.xpath('//button[@data-sc-action="activity.cancel"]')
        self.assertEqual([' '.join(b.text_content().split()) for b in detail], ['Supprimer'])
        resp = self.url_open('/my/activity/cancel', data={
            'csrf_token': self._csrf(), 'activity_id': self.act_team.id,
            'return_url': '/my/activities?tab=today'}, allow_redirects=False)
        self.assertFalse(self.act_team.exists())
        text, _tree = self._page(resp.headers['Location'])
        self.assertIn('Activité supprimée.', text)


@tagged('post_install', '-at_install')
class TestMessagesAnnulerTours1663(Messages1663Common):
    browser_size = '390x844'

    def test_archive_then_undo_tour(self):
        self._post_announcement('Synthetic tour announcement')
        self.start_tour('/my/team?team_id=%s' % self.team_a.id, 'sc_1663_announcement_undo',
                        login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.team_a.announcement, 'Synthetic tour announcement')

    def test_activity_delete_tour(self):
        target = self.act_player
        self.start_tour('/my/activity/%s' % target.id, 'sc_1663_activity_delete', login='pc.tp@example.com')
        self.assertFalse(target.exists())
