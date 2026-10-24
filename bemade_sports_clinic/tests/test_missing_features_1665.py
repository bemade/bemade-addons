"""Task 1665 — missing app features found while documenting. Synthetic
fixtures only.

Acceptance criteria covered here:

* AC-1 Timesheets: with my own editable timesheet on the event, « Add My
  Timesheet » opens it in edit (tour) and the sheet offers « Add another
  timesheet »; the server still accepts a second one (split shifts).
* AC-2 Restore a cancelled event: a therapist gets « Restore event » on the
  cancelled event's page; the restore puts it back to Confirmed, the
  assigned staff get « Le Fit Crew — Event restored: … » (mail, per
  language), it is logged on the event, the « Cancelled » chip is gone; a
  coach gets a 403.
* AC-3 Morning summary opt-out in Settings: the toggle writes the user's own
  ``digest_daily_enabled``; the briefing cron then skips that user only;
  nobody changes another user's preference.
* AC-4 MC's « Medical alerts to validate » list has an « Open » row button
  opening the player form.
* AC-5 Treatment-note injury picker: add and edit offer the SAME list — all
  the player's injuries, the resolved ones last with « (resolved) ».
"""
import json

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Features1665Common(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tree(self, url, status=200):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, url)
        return lxml_html.fromstring(resp.text) if status == 200 else None


@tagged('post_install', '-at_install')
class TestMissingFeatures1665(Features1665Common):

    # -- AC-1 -------------------------------------------------------------
    def test_existing_timesheet_and_add_another(self):
        self._login_tp()
        tree = self._tree('/my/event/%s' % self.event.id)
        holder = tree.xpath('//*[@data-sc-ts-existing-id]')
        self.assertEqual(holder[0].get('data-sc-ts-existing-id'), str(self.timesheet.id))
        submit = tree.xpath('//dialog[@id="sc_ts_add_sheet"]//button[@type="submit"]')[0]
        self.assertEqual(' '.join(submit.text_content().split()), 'Add another timesheet')
        self.assertTrue(tree.xpath('//*[@data-sc-timesheet-id="%s"][@data-sc-edit-card]' % self.timesheet.id))
        resp = self.url_open('/my/event/%s/timesheet/add' % self.event.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertIn('ts_saved=1', resp.headers['Location'])
        self.assertEqual(self.env['sports.event.timesheet'].search_count(
            [('event_id', '=', self.event.id), ('user_id', '=', self.tp.id)]), 2)

    # -- AC-2 -------------------------------------------------------------
    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_restore_cancelled_event(self):
        self.event.sudo().write({'state': 'cancelled'})
        self._login_tp()
        tree = self._tree('/my/event/%s' % self.event.id)
        self.assertTrue(tree.xpath('//button[@data-sc-action="event.restore"]'))
        form = tree.xpath('//dialog[@id="sc_event_restore_sheet"]//form')[0]
        self.assertEqual(form.get('action'), '/my/event/%s/restore' % self.event.id)
        before = self.env['mail.message'].search([('model', '=', 'sports.event'), ('res_id', '=', self.event.id)])
        resp = self.url_open(form.get('action'), data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertIn('restored=1', resp.headers['Location'])
        self.event.invalidate_recordset()
        self.assertEqual(self.event.state, 'confirmed')
        messages = self.env['mail.message'].search(
            [('model', '=', 'sports.event'), ('res_id', '=', self.event.id)]) - before
        notice = messages.filtered(lambda m: self.tp.partner_id in m.notified_partner_ids)
        self.assertEqual(len(notice), 1)
        self.assertEqual(notice.subject, 'Le Fit Crew — Event restored: PC Event')
        self.assertTrue(messages.filtered(lambda m: 'restored via portal' in str(m.body or '')))
        tree = self._tree('/my/event/%s' % self.event.id)
        self.assertFalse(tree.xpath('//button[@data-sc-action="event.restore"]'))
        self.assertFalse(tree.xpath('//span[contains(@class, "o_sc_chip_red")][normalize-space()="Cancelled"]'))
        self.assertTrue(tree.xpath('//button[@data-sc-action="event.cancel"]'))

    @mute_logger('odoo.http')
    def test_restore_refused_for_coach(self):
        self.event.sudo().write({'state': 'cancelled'})
        self._login_coach()
        resp = self.url_open('/my/event/%s/restore' % self.event.id, data={'csrf_token': self._csrf()},
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.event.state, 'cancelled')

    # -- AC-3 -------------------------------------------------------------
    def test_morning_summary_opt_out(self):
        self._login_tp()
        tree = self._tree('/my/app/settings')
        section = tree.xpath('//section[@data-sc-section="settings.morning_summary"]')[0]
        self.assertEqual(section.xpath('.//button[@value="1"]/@aria-pressed'), ['true'])
        self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'digest_daily_enabled': '0',
                                            'redirect': '/my/app/settings'}, allow_redirects=False)
        self.tp.invalidate_recordset()
        self.assertFalse(self.tp.digest_daily_enabled)
        self.assertTrue(self.coach.digest_daily_enabled)
        tree = self._tree('/my/app/settings')
        section = tree.xpath('//section[@data-sc-section="settings.morning_summary"]')[0]
        self.assertEqual(section.xpath('.//button[@value="0"]/@aria-pressed'), ['true'])
        # Never another user's record.
        resp = self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'digest_daily_enabled': '0',
                                                   'user_id': self.coach.id}, allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(self.coach.digest_daily_enabled)
        # The cron skips the opted-out user, not the others.
        (self.tp | self.coach).sudo().write({'digest_send_when_empty': True})
        self.env['res.users']._cron_send_morning_digests(now=fields.Datetime.now())
        messages = self.env['mail.message'].search([('subject', '=like', 'Le Fit Crew — daily briefing%')])
        notified = messages.notified_partner_ids
        self.assertNotIn(self.tp.partner_id, notified)
        self.assertIn(self.coach.partner_id, notified)
        # Back on.
        self.url_open('/my/app/pref', data={'csrf_token': self._csrf(), 'digest_daily_enabled': '1'},
                      allow_redirects=False)
        self.tp.invalidate_recordset()
        self.assertTrue(self.tp.digest_daily_enabled)

    # -- AC-4 -------------------------------------------------------------
    def test_medical_review_list_open_button(self):
        view = self.env.ref('bemade_sports_clinic.sports_patient_view_list_medical_review')
        arch = lxml_html.fromstring(view.arch)
        buttons = arch.xpath('//button[@name="action_view_patient_form"][@type="object"]')
        self.assertEqual(len(buttons), 1)
        action = self.player.action_view_patient_form()
        self.assertEqual((action['res_model'], action['res_id'], action['view_mode']),
                         ('sports.patient', self.player.id, 'form'))

    # -- AC-5 -------------------------------------------------------------
    def test_note_injury_picker_same_list(self):
        resolved = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic old strain'})
        resolved.with_context(mail_notrack=True).write({
            'stage': 'resolved', 'resolution_date': fields.Date.today()})
        note = self.env['sports.treatment.note'].create({
            'patient_id': self.player.id, 'note': 'Synthetic note', 'user_id': self.tp.id})
        self._login_tp()
        tree = self._tree('/my/player?player_id=%s&tab=notes' % self.player.id)
        add = [(o.get('value'), o.text_content().strip())
               for o in tree.xpath('//select[@id="sc_note_injury"]/option') if o.get('value')]
        self.assertEqual(add, [(str(self.injury.id), 'Sprain'),
                               (str(resolved.id), 'Synthetic old strain (resolved)')])
        edits = [json.loads(raw) for raw in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]
        pickers = [p for p in edits if p.get('model') == 'sports.treatment.note' and p.get('field') == 'injury_id'
                   and p.get('recordId', p.get('id')) in (note.id, str(note.id))] or \
                  [p for p in edits if p.get('model') == 'sports.treatment.note' and p.get('field') == 'injury_id']
        self.assertTrue(pickers, 'the note edit picker is on the page')
        options = [tuple(o[:2]) for o in pickers[0]['options'] if o[0]]
        self.assertEqual(options, add, 'add and edit offer the same list')
        self.assertTrue(note)


@tagged('post_install', '-at_install')
class TestMissingFeaturesTour1665(Features1665Common):
    browser_size = '390x844'

    def test_add_my_timesheet_opens_existing(self):
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1665_timesheet_existing', login='pc.tp@example.com')
