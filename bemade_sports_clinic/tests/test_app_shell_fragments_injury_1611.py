"""Task 1611 — injury saves refresh what depends on them (read fragments).
Synthetic fixtures only.

Use case: a therapist changes an injury's status, diagnosis, date, visibility
or consent in its inline card (player page, clinic dossier) or on the injury
page; the card's summary, its order, the « link to an injury » choices, the
treatment notes' linked-injury name and the injury page's title follow at
once — without « Done » and without a reload.

Acceptance criteria:

* AC-I1 Stage / diagnosis / date / visibility / consent -> the card summary
  (dot, title, « date · stage » subtitle, chips) and its read view (the
  « Resolution date » row appears with « Resolved »).
* AC-I2 Card order: the player's injury list is a list fragment whose items
  follow the fresh order (a resolved injury moves after the current ones).
* AC-I3 Diagnosis -> the « Link to Injury » selects (Add note + Document
  upload) and the linked-injury name in the treatment notes' meta line.
* AC-I4 Treatment note date / link / text -> the note's meta line and its
  « modified » stamp, in the server's date format.
* AC-I5 Injury page (task 1616: the open card): diagnosis -> the card's
  summary; the Details / Notes read views are refreshed too.
* AC-I6 Clinic dossier: a resolved injury drops out of « Active injuries »
  (list fragment).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon, FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_clinic_dossier_inline_1590 import ClinicDossier1590Common


@tagged('post_install', '-at_install')
class TestFragmentsInjury1611(FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.write({'injury_date': '2026-01-05'})
        cls.injury_b = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic knee', 'injury_date': '2026-01-01'})
        cls.injury_b.with_context(mail_notrack=True).write({'stage': 'active'})
        cls.note = cls.env['sports.treatment.note'].create({
            'patient_id': cls.player.id, 'injury_id': cls.injury.id,
            'note': 'Synthetic treatment note', 'user_id': cls.tp.id, 'date': '2026-01-10',
        })

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    def _ikey(self, injury, part):
        return 'sports.patient.injury:%s:%s' % (injury.id, part)

    def _pkey(self, part):
        return 'sports.patient:%s:%s' % (self.player.id, part)

    # -- AC-I1 -------------------------------------------------------------
    def test_stage_refreshes_summary_and_read_view(self):
        self._login_tp()
        payload = self._saved(self.injury, 'stage', 'resolved')
        for part in ('summary', 'read'):
            self.assertRefreshes(payload, self._ikey(self.injury, part))
        summary = self._fragment(self._url(), self._ikey(self.injury, 'summary'))
        self.assertTrue(summary.xpath('.//*[contains(@class, "o_sc_tone_green")]'))
        self.assertIn('Resolved', self._text(summary))
        read = self._fragment(self._url(), self._ikey(self.injury, 'read'))
        self.assertIn('Resolution Date', [self._text(dt) for dt in read.xpath('.//dt')])
        self.assertFragmentMatchesPage(self._url(), self._ikey(self.injury, 'summary'))

    def test_other_fields_refresh_summary(self):
        self._login_tp()
        payload = self._saved(self.injury, 'hidden_from_coaches', '1')
        self.assertRefreshes(payload, self._ikey(self.injury, 'summary'))
        summary = self._fragment(self._url(), self._ikey(self.injury, 'summary'))
        self.assertIn('Hidden from coaches', self._text(summary))
        self._saved(self.injury, 'diagnosis', 'Synthetic wrist')
        self._saved(self.injury, 'sc_injury_date', '2026-01-07')
        summary = self._fragment(self._url(), self._ikey(self.injury, 'summary'))
        self.assertIn('Synthetic wrist', self._text(summary))
        self.assertIn('2026', self._text(summary))
        self.assertIn('Consent to complete', self._text(summary))
        self._saved(self.injury, 'parental_consent', 'yes')
        summary = self._fragment(self._url(), self._ikey(self.injury, 'summary'))
        self.assertNotIn('Consent to complete', self._text(summary))
        self.assertFragmentMatchesPage(self._url(), self._ikey(self.injury, 'summary'))

    # -- AC-I2 -------------------------------------------------------------
    def test_card_order_follows_the_stage(self):
        self._login_tp()
        def order():
            node = self._fragment(self._url(), self._pkey('injuries'))
            self.assertEqual(node.get('data-sc-fragment-mode'), 'list')
            return node.xpath('.//*[@data-sc-fragment-item]/@data-sc-fragment-item')
        self.assertEqual(order(), [self._ikey(self.injury, 'card'), self._ikey(self.injury_b, 'card')])
        payload = self._saved(self.injury, 'stage', 'resolved')
        self.assertRefreshes(payload, self._pkey('injuries'))
        self.assertEqual(order(), [self._ikey(self.injury_b, 'card'), self._ikey(self.injury, 'card')])

    # -- AC-I3 -------------------------------------------------------------
    def test_diagnosis_refreshes_choices_and_note_meta(self):
        self._login_tp()
        payload = self._saved(self.injury, 'diagnosis', 'Synthetic shoulder')
        for key in (self._pkey('doc-injury-choices'), self._pkey('note-injury-choices'),
                    'sports.treatment.note:%s:meta' % self.note.id):
            self.assertRefreshes(payload, key)
        for part, tab in (('doc-injury-choices', 'documents'), ('note-injury-choices', 'notes')):
            select = self._fragment(self._url(tab), self._pkey(part))
            self.assertEqual(select.tag, 'select')
            self.assertTrue(any('Synthetic shoulder' in label for label in select.xpath('.//option/text()')), part)
        meta = self._fragment(self._url('notes'), 'sports.treatment.note:%s:meta' % self.note.id)
        self.assertIn('Synthetic shoulder', self._text(meta))

    # -- AC-I4 -------------------------------------------------------------
    def test_note_date_and_link_refresh_meta(self):
        self._login_tp()
        key = 'sports.treatment.note:%s:meta' % self.note.id
        payload = self._saved(self.note, 'date', '2026-03-04')
        self.assertRefreshes(payload, key)
        self.assertRefreshes(payload, 'sports.treatment.note:%s:stamp' % self.note.id)
        self._saved(self.note, 'injury_id', '')
        meta = self._fragment(self._url('notes'), key)
        self.assertIn('General note', self._text(meta))
        self.note.invalidate_recordset()
        self.assertIn(self.note.portal_when_label, self._text(meta))
        self.assertFragmentMatchesPage(self._url('notes'), key)

    # -- AC-I5 -------------------------------------------------------------
    def test_injury_page_title_follows_diagnosis(self):
        # Task 1616: the injury page is the open card — its title is the
        # card's summary, refreshed by a diagnosis save.
        self._login_tp()
        url = '/my/injury/edit?injury_id=%s' % self.injury.id
        resp = self.url_open(url, allow_redirects=False)
        self.assertIn('injury=%s' % self.injury.id, resp.headers.get('Location', ''))
        payload = self._saved(self.injury, 'diagnosis', 'Synthetic elbow')
        for part in ('summary', 'read', 'notes'):
            self.assertRefreshes(payload, self._ikey(self.injury, part))
        summary = self._fragment(self._url(), self._ikey(self.injury, 'summary'))
        self.assertIn('Synthetic elbow', self._text(summary))


@tagged('post_install', '-at_install')
class TestFragmentsDossier1611(FragmentsMixin, ClinicDossier1590Common):

    # -- AC-I6 -------------------------------------------------------------
    def test_resolved_injury_drops_out_of_active_list(self):
        from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon, FragmentsMixin
        self._login_tp()
        key = 'sports.patient:%s:active-injuries' % self.player.id
        item = 'sports.patient.injury:%s:card' % self.injury.id
        tree = self._get(self._dossier_url())[1]
        node = tree.xpath('//*[@data-sc-fragment="%s"]' % key)[0]
        self.assertEqual(node.get('data-sc-fragment-mode'), 'list')
        self.assertTrue(node.xpath('.//*[@data-sc-fragment-item="%s"]' % item))
        payload = self._saved(self.injury, 'stage', 'resolved')
        self.assertRefreshes(payload, key)
        answer = self._fragments(self._dossier_url(), [key])
        self.assertIn(key, answer['missing'] + list(answer['fragments']))
        self.assertNotIn(item, ''.join(answer['fragments'].values()))
