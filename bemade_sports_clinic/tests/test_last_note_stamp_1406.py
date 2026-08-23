"""Task 1406 — « Dernière note le <date> par <auteur> » under the injury note
fields, computed from the note-history audit rows (task 1241).

Acceptance criteria:
- ``last_internal_note_info`` / ``last_external_note_info`` on
  sports.patient.injury read the NEWEST sports.injury.note.history row of
  their scope (by note_datetime, then id — not by id alone) and render
  « Last note on <date> by <author> » with the date in the reader's lang
  (format_date) and the author's name; empty string when the scope has no
  history; « — » stands in for a missing author.
- Portal injury edit page: a treatment professional sees the stamp under
  BOTH note fields; a coach sees the external stamp and never the internal
  one (same guard as the internal notes themselves).
- The #1412 edit-form fragment (clinic modal) and the clinic dossier injury
  cards (#1411) render the same stamps.
- After a save through /my/injury/save the next render shows the new
  author and today's date.
- The backend injury form carries the two stamps (readonly, hidden when
  empty) — the view loads and exposes the values.
- fr_CA: « Dernière note le <date> par <auteur> » on the portal page.

Synthetic fixtures only — this addon's repository is public.

NOT claimed here: placement / look on the page, the modal, the card and the
backend form (phone included) — that is the /dev-review click-through.
"""
from datetime import date, datetime, timedelta

from odoo import Command, fields
from odoo.tests import Form, HttpCase, tagged
from odoo.tools.misc import format_date

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestLastNoteStamp1406(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.History = env['sports.injury.note.history'].sudo()

        # Newest internal row by note_datetime is NOT the highest id: the
        # 2026-03-05 row is created first, the 2026-03-01 row after it.
        cls.History.create({
            'injury_id': cls.injury.id, 'scope': 'internal',
            'content': 'Synthetic internal, newest',
            'author_id': cls.tp.id,
            'note_datetime': datetime(2026, 3, 5, 12, 0),
        })
        cls.History.create({
            'injury_id': cls.injury.id, 'scope': 'internal',
            'content': 'Synthetic internal, older',
            'author_id': cls.coach.id,
            'note_datetime': datetime(2026, 3, 1, 12, 0),
        })
        cls.History.create({
            'injury_id': cls.injury.id, 'scope': 'external',
            'content': 'Synthetic external, older',
            'author_id': cls.tp.id,
            'note_datetime': datetime(2026, 2, 10, 12, 0),
        })
        cls.History.create({
            'injury_id': cls.injury.id, 'scope': 'external',
            'content': 'Synthetic external, newest',
            'author_id': cls.coach.id,
            'note_datetime': datetime(2026, 3, 3, 12, 0),
        })

        # A clinic (TP assigned, player attending) for the dossier card and
        # the #1412 modal fragment.
        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'PC Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.player.id})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _stamp(self, when, author):
        return 'Last note on %s by %s' % (format_date(self.env, when), author)

    @property
    def internal_stamp(self):
        return self._stamp(date(2026, 3, 5), 'PC TP')

    @property
    def external_stamp(self):
        return self._stamp(date(2026, 3, 3), 'PC Coach')

    @property
    def edit_url(self):
        return '/my/injury/edit?injury_id=%s' % self.injury.id

    @property
    def fragment_url(self):
        return '/my/injury/%s/form/fragment?clinic_id=%s&patient=%s' % (
            self.injury.id, self.clinic.id, self.player.id)

    @property
    def dossier_url(self):
        return '/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id)

    # ------------------------------------------------------------------
    # model helper
    # ------------------------------------------------------------------
    def test_newest_row_per_scope(self):
        injury = self.injury
        self.assertEqual(injury._last_note_history('internal').content,
                         'Synthetic internal, newest')
        self.assertEqual(injury._last_note_history('external').content,
                         'Synthetic external, newest')
        self.assertEqual(injury.last_internal_note_info, self.internal_stamp)
        self.assertEqual(injury.last_external_note_info, self.external_stamp)

    def test_empty_when_no_history(self):
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic no-history'})
        self.assertFalse(fresh._last_note_history('internal'))
        self.assertFalse(fresh.last_internal_note_info)
        self.assertFalse(fresh.last_external_note_info)

    def test_scopes_are_independent(self):
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic one-scope'})
        self.History.create({
            'injury_id': fresh.id, 'scope': 'external', 'content': 'only ext',
            'author_id': self.tp.id, 'note_datetime': datetime(2026, 4, 1, 12, 0),
        })
        self.assertFalse(fresh.last_internal_note_info)
        self.assertEqual(fresh.last_external_note_info,
                         self._stamp(date(2026, 4, 1), 'PC TP'))

    def test_author_fallback_when_missing(self):
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic orphan'})
        self.History.create({
            'injury_id': fresh.id, 'scope': 'internal', 'content': 'orphan',
            'author_id': False, 'note_datetime': datetime(2026, 4, 2, 12, 0),
        })
        self.assertEqual(fresh.last_internal_note_info,
                         self._stamp(date(2026, 4, 2), '—'))

    def test_portal_user_can_read_the_stamp(self):
        # compute_sudo: the history model is read-only / rule-gated for portal
        # users, the stamp must still resolve for the coach (external) and
        # the TP (both) as plain field reads.
        as_coach = self.injury.with_user(self.coach)
        self.assertEqual(as_coach.last_external_note_info, self.external_stamp)
        as_tp = self.injury.with_user(self.tp)
        self.assertEqual(as_tp.last_internal_note_info, self.internal_stamp)

    def test_stamp_follows_a_new_note_write(self):
        injury = self.injury
        injury.with_user(self.tp).with_context(mail_notrack=True).write({
            'external_notes': 'Synthetic fresh external'})
        today = fields.Date.context_today(injury.with_user(self.tp))
        self.assertEqual(injury.last_external_note_info, self._stamp(today, 'PC TP'))
        # internal untouched
        self.assertEqual(injury.last_internal_note_info, self.internal_stamp)

    # ------------------------------------------------------------------
    # portal renders
    # ------------------------------------------------------------------
    def test_edit_page_tp_sees_both_stamps(self):
        self._login_tp()
        html = self.url_open(self.edit_url).text
        self.assertIn(self.internal_stamp, html)
        self.assertIn(self.external_stamp, html)

    def test_edit_page_coach_never_sees_internal_stamp(self):
        self._login_coach()
        html = self.url_open(self.edit_url).text
        self.assertIn(self.external_stamp, html)
        self.assertNotIn(self.internal_stamp, html)
        self.assertNotIn('id="internal_notes"', html)

    def test_edit_page_no_stamp_without_history(self):
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic blank'})
        self._login_tp()
        html = self.url_open('/my/injury/edit?injury_id=%s' % fresh.id).text
        self.assertNotIn('Last note on', html)
        self.assertNotIn('o_sc_last_note_stamp', html)

    def test_modal_fragment_carries_the_stamps(self):
        self._login_tp()
        html = self.url_open(self.fragment_url).text
        self.assertIn(self.internal_stamp, html)
        self.assertIn(self.external_stamp, html)

    def test_clinic_card_carries_the_stamps(self):
        self._login_tp()
        html = self.url_open(self.dossier_url).text
        self.assertIn(self.internal_stamp, html)
        self.assertIn(self.external_stamp, html)

    def test_stamp_updates_after_portal_save(self):
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token,
            'injury_id': self.injury.id,
            'partial': '1',
            'external_notes': 'Synthetic note saved from the portal',
        })
        self.assertEqual(resp.status_code, 200)
        today = fields.Date.context_today(self.injury.with_user(self.tp))
        html = self.url_open(self.edit_url).text
        self.assertIn(self._stamp(today, 'PC TP'), html)
        self.assertNotIn(self.external_stamp, html)
        # internal untouched by an external-only save
        self.assertIn(self.internal_stamp, html)

    # ------------------------------------------------------------------
    # backend form
    # ------------------------------------------------------------------
    def test_backend_form_exposes_the_stamps(self):
        with Form(self.injury) as form:
            self.assertEqual(form.last_internal_note_info, self.internal_stamp)
            self.assertEqual(form.last_external_note_info, self.external_stamp)


@tagged('-at_install', 'post_install')
class TestLastNoteStampFrCA1406(HttpCase):
    """The stamp is French for an fr_CA therapist (Python `_()` + the lang's
    date format). Website-aware: with `website` installed the portal language
    follows the website, so fr_CA is made a website language and picked via
    the frontend_lang cookie."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'])
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.org = env['res.partner'].create({'name': 'LN Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'LN Team', 'parent_id': cls.org.id})
        cls.tp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'LN Thérapeute', 'login': 'ln.fr@example.com', 'password': 'ln-fr-ca',
            'lang': 'fr_CA',
            'group_ids': [Command.set([
                env.ref('base.group_portal').id,
                env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'})
        cls.patient = env['sports.patient'].create({'first_name': 'Léa', 'last_name': 'Note'})
        cls.patient.team_ids = [Command.set([cls.team.id])]
        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.patient.id, 'diagnosis': 'Entorse synthétique'})
        cls.injury.with_context(mail_notrack=True).write({'stage': 'active'})
        env['sports.injury.note.history'].sudo().create([{
            'injury_id': cls.injury.id, 'scope': 'internal', 'content': 'interne',
            'author_id': cls.tp.id, 'note_datetime': datetime(2026, 3, 5, 12, 0),
        }, {
            'injury_id': cls.injury.id, 'scope': 'external', 'content': 'externe',
            'author_id': cls.tp.id, 'note_datetime': datetime(2026, 3, 3, 12, 0),
        }])

    def test_stamp_renders_in_french(self):
        self.authenticate('ln.fr@example.com', 'ln-fr-ca')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        html = self.url_open('/my/injury/edit?injury_id=%s' % self.injury.id).text
        fr_env = self.env(context=dict(self.env.context, lang='fr_CA'))
        for when in (date(2026, 3, 5), date(2026, 3, 3)):
            self.assertIn(
                'Dernière note le %s par LN Thérapeute' % format_date(fr_env, when), html)
        self.assertNotIn('Last note on', html)
        # model-level too (the backend form path)
        self.assertEqual(
            self.injury.with_context(lang='fr_CA').last_external_note_info,
            'Dernière note le %s par LN Thérapeute' % format_date(fr_env, date(2026, 3, 3)))
