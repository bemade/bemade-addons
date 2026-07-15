"""Merge Players wizard: conflict surfacing and clinical free-text handling.

Policy agreed with the owner (2026-07-15):
  * Scalar fields -- destination wins where set, sources fill blanks. Where both
    are set and DIFFER, the wizard warns prominently so the user can cancel,
    reconcile on the patient forms, and re-run. The warning is advisory, not a
    hard block: the user may proceed knowingly.
  * Clinical free text -- never discarded. Concatenated under a provenance
    header. Dropping an allergy recorded only on the source is a safety risk,
    not just a data-quality one.

The real records justified both rules: one held a full insurance policy number
while the other held only a bare insurer name, and their allergies recorded the
same drug under two different spellings -- which no automatic rule should
silently pick between.

ACCEPTANCE CRITERIA
-------------------
AC1  A field set on BOTH patients with differing values is reported as a
     conflict before the merge is applied, naming the field, the destination
     value and each source value.
AC2  A field set only on the source is NOT a conflict -- it silently fills the
     destination's blank (that is AC7 of the wizard suite, not a warning).
AC3  Identical values on both patients are NOT reported as conflicts.
AC4  The warning is advisory: proceeding applies destination-wins. The wizard
     must also be cancellable with zero side effects -- nothing written, no
     patient unlinked, no partner merged.
AC5  Conflicts are computed over fields the acting user can actually READ.
     date_of_birth, team_info_notes and allergies are group-restricted to the
     treatment-professional groups (patient.py:72); the check must not leak a
     restricted value into a warning shown to a user who cannot see the field.
AC6  team_info_notes: destination text kept, each source's text appended under a
     '--- Merged from <name> (ID <id>) ---' provenance header. Destination-only
     and source-only cases both behave (no stray header, no leading separator).
AC7  allergies: same concatenation rule. An allergy recorded ONLY on the source
     must appear on the survivor -- this is the safety-critical case.
AC8  Concatenation is not duplicated when both patients carry identical text --
     the survivor must not read 'Peanut allergy / Peanut allergy'.
AC9  Free-text concatenation is applied with tracking disabled, consistent with
     the rest of the merge (team_info_notes is tracked; allergies is not).
AC10 Conflict detection ignores fields the merge resolves by rule rather than by
     precedence: last_consultation_date (max), team_ids (union), and the
     match_status/practice_status pair are never reported as conflicts.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPatientMergeConflicts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.sudo().group_ids = [
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional').id),
            Command.link(cls.env.ref(
                'bemade_sports_clinic.group_sports_clinic_admin').id),
        ]
        cls.team = cls.env['sports.team'].create({'name': 'Braves'})

    def _patient(self, first_name, **vals):
        vals.setdefault('last_name', 'Sampleton')
        vals['first_name'] = first_name
        return self.env['sports.patient'].create(vals)

    def _wizard(self, patients, dst):
        Wizard = self.env['sports.patient.merge.wizard'].with_context(
            active_ids=patients.ids)
        values = Wizard.default_get(list(Wizard._fields))
        values['dst_patient_id'] = dst.id
        return Wizard.create(values)

    def test_differing_scalar_reported_as_conflict(self):
        """AC1."""
        dst = self._patient('Alexandre', date_of_birth='2010-03-01')
        src = self._patient('Alex', date_of_birth='2008-01-01')

        wizard = self._wizard(dst | src, dst)

        self.assertTrue(wizard.has_conflicts, "differing DOB must be flagged")
        self.assertIn('2010-03-01', wizard.conflict_info,
                      "warning must show the value being kept")
        self.assertIn('2008-01-01', wizard.conflict_info,
                      "warning must show the value being discarded")

    def test_source_only_value_is_not_a_conflict(self):
        """AC2."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex', date_of_birth='2008-01-01')

        wizard = self._wizard(dst | src, dst)

        self.assertFalse(wizard.has_conflicts,
                         "filling a blank is not a conflict")

    def test_identical_values_not_reported(self):
        """AC3."""
        dst = self._patient('Alexandre', date_of_birth='2010-03-01')
        src = self._patient('Alex', date_of_birth='2010-03-01')

        wizard = self._wizard(dst | src, dst)

        self.assertFalse(wizard.has_conflicts,
                         "identical values are not a conflict")

    def test_warning_is_advisory_and_cancel_is_clean(self):
        """AC4."""
        dst = self._patient('Alexandre', date_of_birth='2010-03-01')
        src = self._patient('Alex', date_of_birth='2008-01-01')

        wizard = self._wizard(dst | src, dst)
        self.assertTrue(wizard.has_conflicts)

        # Cancelling: merely building the wizard must change nothing.
        self.assertTrue(src.exists(), "source patient must be untouched")
        self.assertEqual(str(src.date_of_birth), '2008-01-01')
        self.assertTrue(src.partner_id.exists())

        # Proceeding anyway is allowed -- the warning does not block.
        wizard.action_merge()
        self.assertEqual(str(dst.date_of_birth), '2010-03-01')
        self.assertFalse(src.exists())

    def test_conflicts_respect_field_group_restrictions(self):
        """AC5: a restricted value must not leak into the warning.

        return_date is NOT group-restricted while date_of_birth and
        team_info_notes are. Conflicting on both proves the filter is
        SELECTIVE: a blanket-empty warning would pass a naive assertNotIn
        while telling us nothing.
        """
        dst = self._patient('Alexandre', date_of_birth='2010-03-01',
                            return_date='2025-12-01',
                            team_info_notes='destination note')
        src = self._patient('Alex', date_of_birth='2008-01-01',
                            return_date='2025-12-15',
                            team_info_notes='source note')

        restricted_user = self.env['res.users'].create({
            'name': 'Clinic User', 'login': 'clinic_user_conflicts',
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
            ])],
        })
        wizard = self._wizard(dst | src, dst)

        # Compute in the RESTRICTED env first. Odoo caches a non-stored compute
        # per (record, field) for the whole transaction, not per user, so
        # reading as admin first poisons the cache and makes this test pass
        # vacuously against a value the restricted user never computed.
        info = wizard.with_user(restricted_user).conflict_info or ''
        wizard.invalidate_recordset(['conflict_info', 'has_conflicts'])

        # Non-vacuity guard: a treatment professional DOES see the restricted
        # fields, so the assertions below fail for the right reason.
        admin_info = wizard.conflict_info or ''
        self.assertIn('2008-01-01', admin_info)
        self.assertIn('Notes', admin_info)

        # The restricted user still gets the conflict they ARE allowed to see...
        self.assertIn('2025-12-15', info,
                      "an unrestricted conflict must still be reported -- an "
                      "empty warning would make this test meaningless")
        # ...but never the restricted ones.
        self.assertNotIn('2008-01-01', info,
                         "date_of_birth is TP-restricted and must not leak")
        self.assertNotIn('Notes', info,
                         "team_info_notes is TP-restricted and must not leak")

    def test_team_info_notes_concatenated_with_provenance(self):
        """AC6: the real insurance-note case."""
        dst = self._patient(
            'Alexandre',
            team_info_notes="no provincial health card --> private insurer, policy POLICY-000123")
        src = self._patient('Alex', team_info_notes='private insurer')
        src_id = src.id

        self._wizard(dst | src, dst).action_merge()

        self.assertIn('POLICY-000123', dst.team_info_notes,
                      "destination note must be kept -- the policy number lives "
                      "only on the destination and is the detail a "
                      "destination-wins-and-discard rule would lose")
        self.assertIn('private insurer', dst.team_info_notes,
                      "source note must be preserved, not discarded")
        self.assertIn(str(src_id), dst.team_info_notes,
                      "appended text must carry provenance")

    def test_destination_only_text_has_no_stray_header(self):
        """AC6: no provenance header when there is nothing to append."""
        dst = self._patient('Alexandre', team_info_notes='only note')
        src = self._patient('Alex')

        self._wizard(dst | src, dst).action_merge()

        self.assertEqual(dst.team_info_notes, 'only note',
                         "a lone note must not gain a provenance header")

    def test_source_only_text_has_no_leading_separator(self):
        """AC6."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex', team_info_notes='source only')

        self._wizard(dst | src, dst).action_merge()

        self.assertTrue(dst.team_info_notes.strip().startswith('---')
                        or dst.team_info_notes.strip() == 'source only',
                        "must not start with a blank separator")
        self.assertIn('source only', dst.team_info_notes)

    def test_source_only_allergy_survives(self):
        """AC7: safety-critical."""
        dst = self._patient('Alexandre')
        src = self._patient('Alex', allergies='Aspirin')

        self._wizard(dst | src, dst).action_merge()

        self.assertIn('Aspirin', dst.allergies or '',
                      "an allergy recorded only on the source must survive")

    def test_differing_allergies_both_survive(self):
        """AC7: the real 'Aspirin' vs 'ASA' case -- both must be kept."""
        dst = self._patient('Alexandre', allergies='Aspirin')
        src = self._patient('Alex', allergies='ASA')

        wizard = self._wizard(dst | src, dst)
        self.assertTrue(wizard.has_conflicts,
                        "differing allergies must be flagged for reconciliation")
        wizard.action_merge()

        self.assertIn('Aspirin', dst.allergies)
        self.assertIn('ASA', dst.allergies)

    def test_identical_text_not_duplicated(self):
        """AC8."""
        dst = self._patient('Alexandre', allergies='Peanut allergy')
        src = self._patient('Alex', allergies='Peanut allergy')

        self._wizard(dst | src, dst).action_merge()

        self.assertEqual(dst.allergies, 'Peanut allergy',
                         "identical text must not be duplicated")

    def test_concatenation_does_not_notify(self):
        """AC9."""
        dst = self._patient('Alexandre', team_info_notes='a')
        src = self._patient('Alex', team_info_notes='b')
        before = self.env['mail.mail'].search_count([])

        self._wizard(dst | src, dst).action_merge()

        self.assertEqual(self.env['mail.mail'].search_count([]), before,
                         "concatenating tracked notes must not notify")

    def test_text_conflicts_do_not_claim_the_value_is_discarded(self):
        """AC1: the warning must not contradict what the merge actually does.

        Raised in human testing: the per-field line said Notes were being
        'discarded' while the footer said notes are 'combined rather than
        discarded'. Notes are never discarded -- they are concatenated.
        """
        dst = self._patient('Alexandre', team_info_notes='destination note')
        src = self._patient('Alex', team_info_notes='source note')

        wizard = self._wizard(dst | src, dst)

        info = wizard.conflict_info
        self.assertTrue(wizard.has_conflicts)
        self.assertIn('combined', info,
                      "a text conflict must say the values are combined")
        self.assertNotIn('discarding', info,
                         "a text conflict must never claim the source text is "
                         "discarded -- it is concatenated")

    def test_scalar_conflicts_still_say_discarded(self):
        """AC1: scalars genuinely are discarded, and must say so."""
        dst = self._patient('Alexandre', date_of_birth='2010-03-01')
        src = self._patient('Alex', date_of_birth='2008-01-01')

        wizard = self._wizard(dst | src, dst)

        self.assertIn('discarding', wizard.conflict_info,
                      "a scalar conflict must be explicit that a value is lost")

    def test_conflict_info_escapes_user_text(self):
        """Notes are user input rendered into an Html field."""
        dst = self._patient('Alexandre', team_info_notes='<b>dst</b>')
        src = self._patient('Alex', team_info_notes='<i>src</i>')

        wizard = self._wizard(dst | src, dst)

        # Text conflicts no longer echo values, but the player names are still
        # interpolated -- ensure nothing user-supplied lands as live markup.
        self.assertNotIn('<b>dst</b>', wizard.conflict_info,
                         "user text must not be injected as live markup")

    def test_rule_resolved_fields_not_reported_as_conflicts(self):
        """AC10."""
        dst = self._patient('Alexandre', last_consultation_date='2025-01-01',
                            match_status='no', practice_status='no',
                            team_ids=[Command.set(self.team.ids)])
        src = self._patient('Alex', last_consultation_date='2025-11-06',
                            match_status='yes', practice_status='yes')

        wizard = self._wizard(dst | src, dst)

        info = wizard.conflict_info or ''
        self.assertNotIn('Last Consultation', info,
                         "last_consultation_date is resolved by the MAX rule")
        self.assertNotIn('2025-11-06', info)
        self.assertFalse(wizard.has_conflicts,
                         "rule-resolved fields must not be reported")
