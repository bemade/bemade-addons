"""Task 1715 — « Possible duplicates » compares the names users see.
Synthetic names only.

Acceptance criteria:

* AC-1 The matcher keys on the player's display name (its contact's name,
  normalised: accents, case, spaces, hyphens). A player whose first / last
  name fields agree with its contact name is compared on those fields
  (first vs last kept, so swapped / near work as before).
* AC-2 A half-overwritten player (contact « A B », fields « C D E ») is
  compared on its contact name, split first word / rest: it never pairs as
  « Same name » with the namesake of its stale fields.
* AC-3 Guard: such a mismatched player never gets the « exact » (nor
  « swapped ») kind — a pair involving it can still be « near ».
* AC-4 Normal exact / swapped / near pairs are unchanged.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.models import sc_name_match as m


@tagged('post_install', '-at_install')
class TestDuplicatePairsTrusted1715(TransactionCase):

    def test_untrusted_never_exact(self):
        pairs = m.duplicate_pairs([
            (1, 'Lucas', 'Synthreid', None, True),
            (2, 'Lucas', 'Synthreid', None, False),
            (3, 'Jonathan', 'Synthwell', None, True),
            (4, 'Synthwell', 'Jonathan', None, False),
        ])
        found = {(a, b): kind for a, b, kind, _same in pairs}
        self.assertEqual(found[(1, 2)], 'near')
        self.assertEqual(found[(3, 4)], 'near')

    def test_four_tuples_unchanged(self):
        pairs = m.duplicate_pairs([
            (1, 'Élodie', 'Synthé', None),
            (2, 'Elodie', 'Synthe', None),
            (3, 'Synthe', 'Elodie', None),
        ])
        found = {(a, b): kind for a, b, kind, _same in pairs}
        self.assertEqual(found[(1, 2)], 'exact')
        self.assertEqual(found[(1, 3)], 'swapped')


@tagged('post_install', '-at_install')
class TestDuplicatesDisplayName1715(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Patient = cls.env['sports.patient']
        # The namesake of the stale fields.
        cls.lucas = Patient.create({'first_name': 'Lucas', 'last_name': 'Synthmain-Reid'})
        # The half-overwritten record: fields « Lucas Synthmain-Reid »,
        # contact « Zackary Synthbuis ».
        cls.broken = Patient.create({'first_name': 'Lucas', 'last_name': 'Synthmain-Reid'})
        cls.env.cr.execute("UPDATE res_partner SET name = %s WHERE id = %s",
                           ('Zackary Synthbuis', cls.broken.partner_id.id))
        cls.broken.partner_id.invalidate_recordset(['name'])
        cls.broken.invalidate_recordset()
        # Its real namesake by contact name.
        cls.zackary = Patient.create({'first_name': 'Zackary', 'last_name': 'Synthbuis'})
        # Normal pairs.
        cls.elodie = Patient.create({'first_name': 'Élodie', 'last_name': 'Synthé-Côté'})
        cls.elodie2 = Patient.create({'first_name': 'elodie', 'last_name': 'Synthe Cote'})
        cls.swap = Patient.create({'first_name': 'Synthé-Côté', 'last_name': 'Élodie'})
        cls.jon = Patient.create({'first_name': 'Jonathan', 'last_name': 'Synthwell'})
        cls.jon2 = Patient.create({'first_name': 'Jonahtan', 'last_name': 'Synthwell'})

    def _pairs(self):
        Dup = self.env['sports.patient.duplicate']
        Dup.action_find_duplicates()
        return {frozenset((p.patient_a_id.id, p.patient_b_id.id)): p.kind for p in Dup.search([])}

    def test_mismatched_record_not_same_name_with_stale_namesake(self):
        self.assertEqual(self.broken.name, 'Zackary Synthbuis')
        pairs = self._pairs()
        self.assertNotIn(frozenset((self.lucas.id, self.broken.id)), pairs)
        # It may pair with the namesake of its DISPLAY name, never as exact.
        kind = pairs.get(frozenset((self.zackary.id, self.broken.id)))
        self.assertIn(kind, (None, 'near'))

    def test_normal_pairs_unchanged(self):
        pairs = self._pairs()
        self.assertEqual(pairs[frozenset((self.elodie.id, self.elodie2.id))], 'exact')
        self.assertEqual(pairs[frozenset((self.elodie.id, self.swap.id))], 'swapped')
        self.assertEqual(pairs[frozenset((self.jon.id, self.jon2.id))], 'near')
