"""Contact-merge guard: refuse partner merges that would destroy patients.

BACKGROUND
----------
sports.patient declares UNIQUE(partner_id). Odoo core's
base.partner.merge.automatic.wizard._update_foreign_keys_generic reacts to a
unique-constraint violation by issuing a raw
    DELETE FROM sports_patient WHERE partner_id IN (<src ids>)
(odoo/addons/base/wizard/base_partner_merge.py:171-180). That bypasses the ORM
and ondelete="restrict", and DB-level CASCADE then takes the patient's injuries,
treatment notes, injury documents and team links with it. This destroyed two
players' clinical history in fitcrew prod on 2026-07-15.

The guard makes that path unreachable: a partner merge that would collide is
refused up front, and staff are pointed at the Merge Players wizard instead.

ACCEPTANCE CRITERIA
-------------------
AC1  Merging contacts linked to more than one patient raises UserError before
     any write occurs; every patient, injury, treatment note, document and team
     link still exists afterwards, and the partners are all still present.
AC2  The error message names the players involved and directs the user to the
     Merge Players action (it must not be a bare constraint traceback).
AC3  Merging contacts linked to exactly one patient still succeeds; the patient
     survives and its partner_id is repointed to the destination partner.
AC4  Merging contacts linked to no patients is unaffected (core behaviour).
AC5  An ARCHIVED patient still counts toward the guard. active_test=False must
     be used: an archived patient continues to occupy UNIQUE(partner_id) and is
     just as deletable by the raw DELETE.
AC6  The guard counts patients, not partners: merging 3 contacts where only the
     destination carries a patient is allowed.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged('post_install', '-at_install')
class TestPatientMergeGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['base.partner.merge.automatic.wizard']
        cls.Partner = cls.env['res.partner']

    def _patient(self, first_name, last_name='Tester'):
        return self.env['sports.patient'].create({
            'first_name': first_name, 'last_name': last_name,
        })

    @mute_logger('odoo.models.unlink', 'odoo.sql_db')
    def test_merge_two_patients_contacts_is_blocked(self):
        """AC1: UserError, and no clinical data is touched."""
        pa = self._patient('Ann')
        pb = self._patient('Bea')
        injury = self.env['sports.patient.injury'].create({
            'patient_id': pb.id, 'diagnosis': 'Sprain',
            'injury_date': '2025-10-09', 'stage': 'active',
        })
        note = self.env['sports.treatment.note'].create({
            'patient_id': pb.id, 'note': 'ice', 'date': '2025-10-10',
        })
        partner_ids = (pa.partner_id | pb.partner_id).ids

        with self.assertRaises(UserError):
            self.Wizard._merge(partner_ids, dst_partner=pa.partner_id)

        self.assertTrue(pa.exists() and pb.exists(), "a patient was destroyed")
        self.assertTrue(injury.exists(), "injury cascade-deleted")
        self.assertTrue(note.exists(), "treatment note cascade-deleted")
        self.assertTrue(pa.partner_id.exists() and pb.partner_id.exists(),
                        "a partner was merged away despite the refusal")

    @mute_logger('odoo.models.unlink', 'odoo.sql_db')
    def test_block_message_names_players_and_points_to_wizard(self):
        """AC2."""
        pa = self._patient('Ann', 'Sampleton')
        pb = self._patient('Bea', 'Sampleton')

        with self.assertRaises(UserError) as ctx:
            self.Wizard._merge((pa.partner_id | pb.partner_id).ids,
                               dst_partner=pa.partner_id)

        message = str(ctx.exception)
        self.assertIn('Ann Sampleton', message, "message must name the players")
        self.assertIn('Bea Sampleton', message, "message must name the players")
        self.assertIn('Merge Players', message,
                      "message must point to the Merge Players route")

    def test_merge_single_patient_contacts_still_works(self):
        """AC3: the one legitimate case core handles correctly."""
        patient = self._patient('Solo')
        dst = self.Partner.create({'name': 'Solo Duplicate'})

        self.Wizard._merge((dst | patient.partner_id).ids, dst_partner=dst)

        self.assertTrue(patient.exists(), "the only patient was destroyed")
        self.assertEqual(patient.partner_id, dst,
                         "patient should be repointed at the destination")

    def test_merge_non_patient_contacts_unaffected(self):
        """AC4: regression guard on ordinary partner merges."""
        a = self.Partner.create({'name': 'Plain A'})
        b = self.Partner.create({'name': 'Plain B'})

        self.Wizard._merge((a | b).ids, dst_partner=a)

        self.assertTrue(a.exists(), "destination partner should survive")
        self.assertFalse(b.exists(), "source partner should be merged away")

    @mute_logger('odoo.models.unlink', 'odoo.sql_db')
    def test_archived_patient_counts_toward_guard(self):
        """AC5: the case an active_test-naive implementation would miss."""
        active_patient = self._patient('Active')
        archived_patient = self._patient('Archived')
        archived_patient.active = False
        self.assertFalse(archived_patient.active, "fixture must be archived")

        with self.assertRaises(UserError):
            self.Wizard._merge(
                (active_patient.partner_id | archived_patient.partner_id).ids,
                dst_partner=active_patient.partner_id,
            )

        self.assertTrue(
            archived_patient.exists(),
            "archived patient was destroyed -- it still occupies "
            "UNIQUE(partner_id) and must count toward the guard",
        )

    def test_three_contacts_one_patient_allowed(self):
        """AC6: guard is not over-eager."""
        patient = self._patient('Only')
        dup_a = self.Partner.create({'name': 'Only Dup A'})
        dup_b = self.Partner.create({'name': 'Only Dup B'})

        self.Wizard._merge((patient.partner_id | dup_a | dup_b).ids,
                           dst_partner=patient.partner_id)

        self.assertTrue(patient.exists(), "patient should survive")
        self.assertFalse(dup_a.exists(), "duplicate A should be merged away")
        self.assertFalse(dup_b.exists(), "duplicate B should be merged away")
