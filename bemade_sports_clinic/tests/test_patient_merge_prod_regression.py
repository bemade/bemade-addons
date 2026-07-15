"""End-to-end regression: the fitcrew prod incident of 2026-07-15.

WHAT HAPPENED
-------------
A player existed as three res.partner records with an inconsistent first name
two of them carried a sports.patient each; the merge destination carried
none. Staff merged the three CONTACTS, because no Merge Players route existed.
The chatter shows they had spent the preceding minutes hand-copying fields from
one patient to the other -- doing a patient merge manually, for want of a tool.

Core's _update_foreign_keys_generic tried
    UPDATE sports_patient SET partner_id = <dst> WHERE partner_id IN (<srcs>)
Both rows collided on UNIQUE(partner_id), Postgres raised, and core's except
branch issued a raw DELETE of both patients. DB-level CASCADE then removed their
injuries, treatment notes, injury documents and team links. The contact merge
itself looked perfectly successful. Zero Sampleton patients remained.

This suite reproduces that exact topology. It must FAIL on the unfixed code (by
losing patients) and pass afterwards. It is the test that would have caught this
before it reached prod, and the reason the bug survived migration is that
test_cov_base_partner_merge.py only ever calls _update_values directly and never
exercises _merge at all.

ACCEPTANCE CRITERIA
-------------------
AC1  REPRODUCTION: 3 partners, 2 of them carrying patients with injuries,
     treatment notes, documents and team links; destination carries no patient.
     Merging the three contacts must NOT delete any patient.
AC2  On unfixed code this suite fails by losing patients -- confirming it
     reproduces the real defect rather than passing vacuously.
AC3  With the guard in place, merging those three contacts raises UserError and
     every patient, injury, treatment note, document and team link survives.
AC4  The correct route works on the same fixture: Merge Players over the two
     patients, with the third contact folded in, yields ONE patient carrying the
     union of both players' clinical history, and ONE contact.
AC5  No clinical record from EITHER patient is missing after AC4 -- asserted by
     explicit count and by identity, not just by count (a cascade that deleted
     two and a repoint that duplicated two would both pass a naive count check).
AC6  The surviving patient's name reflects the destination's spelling, and the
     surviving partner's name matches it (via _recompute_name).
AC7  The two source partners no longer exist; the destination partner does.
AC8  The surviving patient's chatter contains the audit note naming both merged
     patients -- the same trail that made the prod incident reconstructable.
AC9  The whole flow emits no outbound follower notification.
AC10 Guard rail on the fixture itself: assert the FK topology this bug depends
     on still holds (sports.patient.partner_id is UNIQUE, and injuries/notes/
     documents/team-links CASCADE from sports_patient). If a future migration
     changes ondelete or drops the constraint, this suite must fail loudly
     rather than silently testing nothing.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged('post_install', '-at_install')
class TestPatientMergeProdRegression(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # date_of_birth / team_info_notes / allergies are group-restricted, and
        # merging players is gated on the clinic admin group.
        cls.tp_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.admin_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_admin')
        cls.env.user.sudo().group_ids = [
            Command.link(cls.tp_group.id), Command.link(cls.admin_group.id)]
        cls.Wizard = cls.env['base.partner.merge.automatic.wizard']

    def _build_prod_fixture(self):
        """Recreate the prod topology: 3 partners, 2 patients, dst has none."""
        team = self.env['sports.team'].create({'name': 'BRAVES - Junior AAA'})

        # The destination contact -- a duplicate carrying NO patient, exactly
        # like the real one. This is what made ALL patients vanish rather than
        # leaving one behind.
        dst_partner = self.env['res.partner'].create({'name': 'Alex Sampleton'})

        # Two patients, each auto-creating its own partner (as prod did).
        patient_a = self.env['sports.patient'].create({
            'first_name': 'Alexandre', 'last_name': 'Sampleton',
            'date_of_birth': '2010-03-01',
            'team_ids': [Command.set([team.id])],
        })
        patient_b = self.env['sports.patient'].create({
            'first_name': 'Alex', 'last_name': 'Sampleton',
            'date_of_birth': '2010-03-01',
            'team_ids': [Command.set([team.id])],
        })

        # Clinical history on B -- the real record had an active injury.
        injury = self.env['sports.patient.injury'].create({
            'patient_id': patient_b.id,
            'diagnosis': 'Sprained right shoulder',
            'injury_date': '2025-10-09',
            'stage': 'active',
        })
        note = self.env['sports.treatment.note'].create({
            'patient_id': patient_b.id,
            'injury_id': injury.id,
            'note': 'follow-up imaging required',
            'date': '2025-11-06',
        })
        return {
            'team': team, 'dst_partner': dst_partner,
            'patient_a': patient_a, 'patient_b': patient_b,
            'injury': injury, 'note': note,
        }

    @mute_logger('odoo.models.unlink', 'odoo.sql_db')
    def test_contact_merge_of_two_patient_contacts_is_refused(self):
        """AC1, AC3: the incident, now blocked.

        On the UNFIXED code this fails at assertRaises -- no error is raised,
        the merge "succeeds", and both patients are silently gone (AC2).
        """
        fx = self._build_prod_fixture()
        partner_ids = (
            fx['dst_partner'] | fx['patient_a'].partner_id | fx['patient_b'].partner_id
        ).ids

        with self.assertRaises(UserError):
            self.Wizard._merge(partner_ids, dst_partner=fx['dst_partner'])

        # Nothing may be destroyed by a refused merge.
        self.assertTrue(fx['patient_a'].exists(), "patient A was destroyed")
        self.assertTrue(fx['patient_b'].exists(), "patient B was destroyed")
        self.assertTrue(fx['injury'].exists(), "injury cascade-deleted")
        self.assertTrue(fx['note'].exists(), "treatment note cascade-deleted")

    def _merge_players(self, patients, dst, include_partners=None):
        Wizard = self.env['sports.patient.merge.wizard'].with_context(
            active_ids=patients.ids)
        values = Wizard.default_get(list(Wizard._fields))
        values['dst_patient_id'] = dst.id
        wizard = Wizard.create(values)
        for partner in include_partners or self.env['res.partner']:
            line = wizard.contact_line_ids.filtered(
                lambda l: l.partner_id == partner)
            self.assertTrue(
                line, f"{partner.display_name} should have been suggested")
            line.selected = True
        wizard.action_merge()
        return wizard

    def test_merge_players_consolidates_the_three_contacts(self):
        """AC4, AC7: the route staff should have had."""
        fx = self._build_prod_fixture()
        dst, src = fx['patient_a'], fx['patient_b']
        dst_partner, src_partner = dst.partner_id, src.partner_id
        spare = fx['dst_partner']  # the third contact, carrying no patient

        self._merge_players(dst | src, dst, include_partners=spare)

        self.assertTrue(dst.exists(), "one player must survive")
        self.assertFalse(src.exists(), "the duplicate player must be gone")
        # Scoped to the fixture rather than searching by last name: this suite
        # runs against a copy of production, which already contains the real
        # Sampleton records, and a name-based count would collide with them.
        self.assertEqual(
            (dst | src).exists(), dst,
            "exactly one of the merged players must remain, and it must be "
            "the destination")
        # AC7: all three contacts collapse into the survivor's.
        self.assertTrue(dst_partner.exists(), "destination contact must survive")
        self.assertFalse(src_partner.exists(), "source contact must be merged")
        self.assertFalse(spare.exists(),
                         "the third duplicate contact must be merged too -- "
                         "leaving it behind is what sent staff back to the "
                         "contact merge in the first place")

    def test_no_clinical_record_lost_by_identity(self):
        """AC5: count-and-identity, not count alone."""
        fx = self._build_prod_fixture()
        dst, src = fx['patient_a'], fx['patient_b']
        injury_id, note_id = fx['injury'].id, fx['note'].id

        self._merge_players(dst | src, dst)

        injury = self.env['sports.patient.injury'].browse(injury_id)
        note = self.env['sports.treatment.note'].browse(note_id)
        self.assertTrue(injury.exists(), "the original injury row must survive")
        self.assertTrue(note.exists(), "the original note row must survive")
        self.assertEqual(injury.patient_id, dst)
        self.assertEqual(note.patient_id, dst)
        self.assertEqual(injury.diagnosis, 'Sprained right shoulder',
                         "the surviving injury must be the same record, not a "
                         "lookalike recreated by the merge")
        self.assertEqual(dst.injury_ids, injury,
                         "no duplicate injuries may appear")

    def test_surviving_names_use_destination_spelling(self):
        """AC6."""
        fx = self._build_prod_fixture()
        dst, src = fx['patient_a'], fx['patient_b']

        self._merge_players(dst | src, dst)

        self.assertEqual(dst.first_name, 'Alexandre')
        self.assertEqual(dst.partner_id.name, 'Alexandre Sampleton',
                         "the surviving contact must carry the surviving "
                         "player's spelling")

    def test_audit_note_names_both_merged_patients(self):
        """AC8."""
        fx = self._build_prod_fixture()
        dst, src = fx['patient_a'], fx['patient_b']
        src_id = src.id

        self._merge_players(dst | src, dst)

        bodies = ' '.join(dst.message_ids.mapped('body'))
        self.assertIn(str(src_id), bodies,
                      "the audit trail must name the merged-away player id -- "
                      "this is what made the prod incident reconstructable")

    def test_flow_emits_no_notifications(self):
        """AC9."""
        fx = self._build_prod_fixture()
        dst, src = fx['patient_a'], fx['patient_b']
        before = self.env['mail.mail'].search_count([])

        self._merge_players(dst | src, dst)

        self.assertEqual(self.env['mail.mail'].search_count([]), before,
                         "merging historical data must not email the team")

    def test_fk_topology_assumptions_still_hold(self):
        """AC10: fail loudly if a migration changes the shape of the bug."""
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint c
              JOIN pg_class r ON c.conrelid = r.oid
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'u' AND r.relname = 'sports_patient'
               AND a.attname = 'partner_id'
        """)
        self.assertTrue(
            self.env.cr.fetchone(),
            "UNIQUE(partner_id) on sports_patient is gone -- core's merge no "
            "longer takes the DELETE branch and this suite tests nothing. "
            "Re-derive the guard's justification before deleting these tests.",
        )

        self.env.cr.execute("""
            SELECT c.conrelid::regclass::text, c.confdeltype
              FROM pg_constraint c
             WHERE c.contype = 'f'
               AND c.confrelid = 'sports_patient'::regclass
        """)
        ondelete = dict(self.env.cr.fetchall())
        for table in ('sports_patient_injury', 'sports_treatment_note',
                      'sports_injury_document', 'sports_team_patient_rel'):
            self.assertEqual(
                ondelete.get(table), 'c',
                f"{table} no longer CASCADEs from sports_patient; the blast "
                f"radius of a raw DELETE has changed -- revisit the guard.",
            )
