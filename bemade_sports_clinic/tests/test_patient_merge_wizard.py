"""Merge Players wizard: consolidating two patients into one.

The route staff actually needed. Merging duplicate CONTACTS was only ever a
workaround for the absence of this. The wizard consolidates the patients first,
then delegates the res.partner half to Odoo's core merge wizard -- by which
point only one patient remains, so the contact-merge guard passes naturally and
there is no bypass flag or second code path.

ACCEPTANCE CRITERIA
-------------------
AC1  Merging 2 patients leaves exactly 1 patient. The destination survives with
     its id intact (it is the record staff have open and linked to elsewhere).
AC2  All children repoint to the destination and NONE are lost:
     injuries (sports.patient.injury), treatment notes (sports.treatment.note),
     injury documents (sports.injury.document), emergency contacts
     (sports.patient.contact -- note its patient_id has no ondelete, so a naive
     unlink orphans them silently rather than failing loudly).
AC3  Injuries and their dependent notes/documents repoint in ONE transaction.
     sports.treatment.note._check_injury_patient_match and
     sports.injury.document._check_injury_belongs_to_patient both assert that
     injury.patient_id == record.patient_id, so a partial repoint raises.
AC4  team_ids is the UNION of all merged patients' teams; date_left_last_team is
     re-derived afterwards via _sync_teamless_state (teamless <=> date set).
AC5  Source patients are unlinked only AFTER their children have moved -- the
     unlink must never cascade a single clinical record away.
AC6  The source patients' res.partner records are merged into the destination's
     partner via base.partner.merge.automatic.wizard; no orphan partners remain.
AC7  Scalar resolution: destination wins where it has a value; sources fill
     blanks only. No field the destination left empty is discarded.
AC8  last_consultation_date takes the MAX across all merged patients, NOT the
     destination's. It drives the Law 25 retention clock, and taking a stale
     destination value could prematurely age out a record that was in fact seen
     more recently.
AC9  match_status and practice_status move together as a PAIR from the
     destination. constrain_match_and_practice_status (patient.py:332) allows
     only (yes,yes), (no,yes), (no,no_contact), (no,no) -- resolving them
     independently can synthesise an invalid combination such as (yes,no).
AC10 The merge fires NO outbound notification to followers. last_consultation_date,
     match_status, practice_status, predicted_return_date and return_date are all
     in external_tracking_fields (patient.py:10) and email the team on change;
     merge writes must use tracking_disable.
AC11 Chatter is preserved: the source patients' mail.message history, activities
     and followers move to the destination rather than being orphaned by res_id.
AC12 An audit note is posted on the destination naming each merged-away patient
     and its id -- the Law 25 trail, and the thing that let us reconstruct the
     prod incident at all.
AC13 first_name/last_name resolve from the destination and the surviving
     partner's name is recomputed through _recompute_name (which threads the
     patient_update context past the res_partner.write guard at res_partner.py:37).
AC14 Merging is idempotent-safe: a wizard run over a single patient, or with the
     destination not among the selected patients, raises rather than no-oping.
"""

import base64

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged('post_install', '-at_install')
class TestPatientMergeWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.sudo().group_ids = [
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_admin').id),
        ]
        cls.team_a = cls.env['sports.team'].create({'name': 'Braves Junior AAA'})
        cls.team_b = cls.env['sports.team'].create({'name': 'Braves Midget'})

    def _patient(self, first_name, **vals):
        vals.setdefault('last_name', 'Sampleton')
        vals['first_name'] = first_name
        return self.env['sports.patient'].create(vals)

    def _merge(self, patients, dst):
        wizard = self.env['sports.patient.merge.wizard'].with_context(
            active_ids=patients.ids)
        values = wizard.default_get(list(wizard._fields))
        values['dst_patient_id'] = dst.id
        return wizard.create(values).action_merge()

    def test_merge_leaves_one_patient_destination_survives(self):
        """AC1."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dst_id = dst.id

        self._merge(dst | src, dst)

        self.assertTrue(dst.exists(), "destination must survive with its id")
        self.assertEqual(dst.id, dst_id, "destination id must not change")
        self.assertFalse(src.exists(), "source patient should be merged away")

    def test_all_children_repoint_to_destination(self):
        """AC2: injuries, notes, documents, emergency contacts."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': src.id, 'diagnosis': 'Sprained right shoulder',
            'injury_date': '2025-10-09', 'stage': 'active',
        })
        note = self.env['sports.treatment.note'].create({
            'patient_id': src.id, 'injury_id': injury.id,
            'note': 'follow-up imaging required', 'date': '2025-11-06',
        })
        doc = self.env['sports.injury.document'].create({
            'name': 'IRM', 'patient_id': src.id, 'injury_id': injury.id,
            'file_content': base64.b64encode(b'x'), 'category': 'medical_imaging',
        })
        contact = self.env['sports.patient.contact'].create({
            'patient_id': src.id, 'name': 'Father', 'contact_type': 'father',
        })

        self._merge(dst | src, dst)

        for record, label in ((injury, 'injury'), (note, 'treatment note'),
                              (doc, 'document'), (contact, 'emergency contact')):
            self.assertTrue(record.exists(), f"{label} was destroyed")
            self.assertEqual(record.patient_id, dst,
                             f"{label} did not repoint to the destination")

    def test_injury_and_dependents_repoint_atomically(self):
        """AC3: the constraint that punishes a partial repoint.

        Moving a note before its injury raises ValidationError. This asserts the
        merge orders them correctly rather than tripping its own constraints.
        """
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': src.id, 'diagnosis': 'Sprain',
            'injury_date': '2025-10-09', 'stage': 'active',
        })
        notes = self.env['sports.treatment.note']
        for day in ('2025-10-10', '2025-10-11', '2025-10-12'):
            notes |= self.env['sports.treatment.note'].create({
                'patient_id': src.id, 'injury_id': injury.id,
                'note': f'note {day}', 'date': day,
            })

        self._merge(dst | src, dst)

        self.assertEqual(injury.patient_id, dst)
        for note in notes:
            self.assertEqual(note.injury_id.patient_id, note.patient_id,
                             "note and its injury disagree on the patient")

    def test_team_ids_union_and_date_left_last_team_resync(self):
        """AC4."""
        dst = self._patient('Alexandre', team_ids=[Command.set(self.team_a.ids)])
        src = self._patient('Alex', team_ids=[Command.set(self.team_b.ids)])

        self._merge(dst | src, dst)

        self.assertEqual(dst.team_ids, self.team_a | self.team_b,
                         "teams should be the union of both players'")
        self.assertFalse(dst.date_left_last_team,
                         "a player with teams must not carry a left-team date")

    def test_teamless_merge_stamps_retention_clock(self):
        """AC4: the teamless <=> date-set invariant holds after merging too."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        self._merge(dst | src, dst)

        self.assertTrue(dst.date_left_last_team,
                        "a teamless player must carry a left-team date")

    def test_sources_unlinked_after_children_moved(self):
        """AC5: no cascade takes clinical data."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': src.id, 'diagnosis': 'Sprain',
            'injury_date': '2025-10-09', 'stage': 'active',
        })
        injury_id = injury.id

        self._merge(dst | src, dst)

        self.assertFalse(src.exists(), "source should be gone")
        self.assertTrue(
            self.env['sports.patient.injury'].browse(injury_id).exists(),
            "injury was cascade-deleted with the source patient",
        )

    def test_source_partners_merged_into_destination_partner(self):
        """AC6."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        dst_partner, src_partner = dst.partner_id, src.partner_id

        self._merge(dst | src, dst)

        self.assertTrue(dst_partner.exists(), "destination contact must survive")
        self.assertFalse(src_partner.exists(),
                         "source contact should be merged away, not orphaned")
        self.assertEqual(dst.partner_id, dst_partner)

    def test_scalar_destination_wins_sources_fill_blanks(self):
        """AC7."""
        dst = self._patient('Alexandre', date_of_birth='2010-03-01')
        src = self._patient('Alex', date_of_birth='2008-01-01',
                            return_date='2025-12-01')

        self._merge(dst | src, dst)

        self.assertEqual(str(dst.date_of_birth), '2010-03-01',
                         "destination value must win where set")
        self.assertEqual(str(dst.return_date), '2025-12-01',
                         "source must fill a field the destination left blank")

    def test_last_consultation_date_takes_max(self):
        """AC8: Law 25 retention clock.

        The real records had exactly this shape: the destination blank, the
        source consulted on 2025-11-06.
        """
        dst = self._patient('Alexandre', last_consultation_date='2025-01-01')
        src = self._patient('Alex', last_consultation_date='2025-11-06')

        self._merge(dst | src, dst)

        self.assertEqual(
            str(dst.last_consultation_date), '2025-11-06',
            "must take the most recent consultation, not the destination's -- "
            "a stale value prematurely ages out the retention clock",
        )

    def test_last_consultation_date_max_when_destination_blank(self):
        """AC8: destination blank is the case that bit prod."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex', last_consultation_date='2025-11-06')

        self._merge(dst | src, dst)

        self.assertEqual(str(dst.last_consultation_date), '2025-11-06')

    def test_status_pair_stays_valid(self):
        """AC9: never synthesise an invalid (match, practice) combination."""
        dst = self._patient('Alexandre', match_status='no', practice_status='no')
        src = self._patient('Alex', match_status='yes', practice_status='yes')

        self._merge(dst | src, dst)

        self.assertEqual((dst.match_status, dst.practice_status), ('no', 'no'),
                         "the destination's status pair must be kept intact")
        # Would raise ValidationError if the pair were invalid.
        dst.constrain_match_and_practice_status()

    def test_merge_sends_no_follower_notifications(self):
        """AC10."""
        dst = self._patient('Alexandre', team_ids=[Command.set(self.team_a.ids)])
        src = self._patient('Alex', last_consultation_date='2025-11-06',
                            team_ids=[Command.set(self.team_b.ids)])
        before = self.env['mail.mail'].search_count([])

        self._merge(dst | src, dst)

        self.assertEqual(
            self.env['mail.mail'].search_count([]), before,
            "the merge queued outbound mail -- external_tracking_fields "
            "notify the team, so merge writes must be tracking-disabled",
        )

    def test_chatter_and_followers_move_to_destination(self):
        """AC11."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        src.message_post(body='historical note', message_type='comment')
        src_messages = self.env['mail.message'].search([
            ('model', '=', 'sports.patient'), ('res_id', '=', src.id)])
        self.assertTrue(src_messages, "fixture must have chatter to move")
        message_ids = src_messages.ids

        self._merge(dst | src, dst)

        moved = self.env['mail.message'].browse(message_ids)
        for message in moved:
            self.assertEqual(message.res_id, dst.id,
                             "chatter was orphaned instead of moved")

    def test_audit_note_posted_on_destination(self):
        """AC12."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        src_id, src_name = src.id, src.display_name

        self._merge(dst | src, dst)

        bodies = ' '.join(dst.message_ids.mapped('body'))
        self.assertIn(str(src_id), bodies,
                      "audit note must record the merged-away player's id")
        self.assertIn(src_name.split()[0], bodies,
                      "audit note must name the merged-away player")

    def test_audit_note_renders_as_html_not_escaped_tags(self):
        """AC12: the note must READ as prose, not show raw markup.

        Mail bodies escape plain strings -- a str body renders as literal
        '&lt;p&gt;' text in the chatter. Caught by human testing: substring
        assertions pass just as happily on escaped markup, so they never saw it.
        """
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        self._merge(dst | src, dst)

        body = dst.message_ids[0].body
        self.assertNotIn('&lt;p&gt;', body,
                         "audit note is escaped -- the user sees raw HTML tags")
        self.assertNotIn('&lt;ul&gt;', body)
        self.assertIn('<p>', body, "audit note must contain real markup")

    def test_audit_note_escapes_player_names(self):
        """AC12: names are user input and must not inject markup."""
        dst = self._patient('Alexandre')
        src = self._patient('<b>Bold</b>')

        self._merge(dst | src, dst)

        body = dst.message_ids[0].body
        self.assertNotIn('<b>Bold</b>', body,
                         "a player name must not be injected as live markup")
        self.assertIn('&lt;b&gt;Bold', body, "the name must appear, escaped")

    def test_partner_name_recomputed_from_destination(self):
        """AC13."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')

        self._merge(dst | src, dst)

        self.assertEqual(dst.first_name, 'Alexandre')
        self.assertEqual(
            dst.partner_id.name, 'Alexandre Sampleton',
            "surviving contact name must match the surviving player's name",
        )

    @mute_logger('odoo.models.unlink')
    def test_invalid_selections_raise(self):
        """AC14."""
        solo = self._patient('Solo')
        other = self._patient('Other')
        outsider = self._patient('Outsider')

        with self.assertRaises(UserError):
            self.env['sports.patient.merge.wizard'].with_context(
                active_ids=solo.ids).default_get(['patient_ids'])

        wizard = self.env['sports.patient.merge.wizard'].create({
            'patient_ids': [Command.set((solo | other).ids)],
            'dst_patient_id': outsider.id,
        })
        with self.assertRaises(UserError):
            wizard.action_merge()

    def test_wizard_form_view_is_usable(self):
        """The view must render and save -- catches missing/misnamed fields."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex')
        with Form(self.env['sports.patient.merge.wizard'].with_context(
                active_ids=(dst | src).ids)) as form:
            form.dst_patient_id = dst
        wizard = form.save()
        self.assertEqual(wizard.patient_ids, dst | src)
        wizard.action_merge()
        self.assertFalse(src.exists())
