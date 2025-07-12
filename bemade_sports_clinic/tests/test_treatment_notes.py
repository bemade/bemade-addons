from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from datetime import date

@tagged('post_install', '-at_install')
class TestTreatmentNotes(TransactionCase):
    """Test the behavior of treatment notes after refactoring to be patient-centric."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get treatment professional group
        cls.treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.portal_treatment_prof_group = cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Create test users
        cls.user_therapist = cls.env['res.users'].create({
            'name': 'Test Therapist',
            'login': 'test_therapist',
            'email': 'therapist@example.com',
            'groups_id': [(6, 0, [cls.treatment_prof_group.id])],
        })
        
        # Create test patient
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'Test',
            'last_name': 'Patient',
            'email': 'test@example.com',
        })
        
        # Create test injury
        cls.injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.patient.id,
            'diagnosis': 'Test Injury',
            'injury_date': date.today(),
        })
    
    def test_injury_note_creation(self):
        """Test creating a treatment note linked to an injury."""
        # Create note linked to an injury
        note = self.env['sports.treatment.note'].create({
            'patient_id': self.patient.id,
            'injury_id': self.injury.id,
            'note': 'Test note for injury',
            'date': date.today(),
            'user_id': self.user_therapist.id,
        })
        
        # Verify note is correctly linked to both patient and injury
        self.assertEqual(note.patient_id, self.patient)
        self.assertEqual(note.injury_id, self.injury)
        self.assertEqual(note.note_type, 'injury')
    
    def test_general_note_creation(self):
        """Test creating a general treatment note (not linked to an injury)."""
        # Create note linked only to patient
        note = self.env['sports.treatment.note'].create({
            'patient_id': self.patient.id,
            'note': 'General patient note',
            'date': date.today(),
            'user_id': self.user_therapist.id,
        })
        
        # Verify note is correctly linked to patient only
        self.assertEqual(note.patient_id, self.patient)
        self.assertFalse(note.injury_id)
        self.assertEqual(note.note_type, 'general')
    
    def test_note_constraint(self):
        """Test constraint that ensures injury belongs to patient."""
        # Create another patient
        other_patient = self.env['sports.patient'].create({
            'first_name': 'Other',
            'last_name': 'Patient',
            'email': 'other@example.com',
        })
        
        # Create injury for other patient
        other_injury = self.env['sports.patient.injury'].create({
            'patient_id': other_patient.id,
            'diagnosis': 'Other Injury',
            'injury_date': date.today(),
        })
        
        # Attempt to create note with mismatched patient and injury
        with self.assertRaises(ValidationError):
            self.env['sports.treatment.note'].create({
                'patient_id': self.patient.id,
                'injury_id': other_injury.id,  # This injury belongs to other_patient
                'note': 'This should fail',
                'date': date.today(),
                'user_id': self.user_therapist.id,
            })
    
    def test_patient_treatment_note_count(self):
        """Test the computed field treatment_note_count on patient."""
        # Initial count should be zero
        self.assertEqual(self.patient.treatment_note_count, 0)
        
        # Create 3 notes (2 general, 1 injury-specific)
        for i in range(2):
            self.env['sports.treatment.note'].create({
                'patient_id': self.patient.id,
                'note': f'General note {i+1}',
                'date': date.today(),
                'user_id': self.user_therapist.id,
            })
            
        self.env['sports.treatment.note'].create({
            'patient_id': self.patient.id,
            'injury_id': self.injury.id,
            'note': 'Injury note',
            'date': date.today(),
            'user_id': self.user_therapist.id,
        })
        
        # Refresh patient record to ensure computed fields are up-to-date
        self.patient.invalidate_model(['treatment_note_count'])
        
        # Verify count
        self.assertEqual(self.patient.treatment_note_count, 3)
        
    def test_injury_treatment_note_count(self):
        """Test that injury only counts notes that are linked to it."""
        # Initial count should be zero
        self.assertEqual(len(self.injury.treatment_note_ids), 0)
        
        # Create a general patient note (not linked to injury)
        self.env['sports.treatment.note'].create({
            'patient_id': self.patient.id,
            'note': 'General patient note',
            'date': date.today(),
            'user_id': self.user_therapist.id,
        })
        
        # Create an injury-specific note
        self.env['sports.treatment.note'].create({
            'patient_id': self.patient.id,
            'injury_id': self.injury.id,
            'note': 'Injury note',
            'date': date.today(),
            'user_id': self.user_therapist.id,
        })
        
        # Refresh injury record
        self.injury.invalidate_model(['treatment_note_ids'])
        
        # Verify that only the injury-specific note is counted
        self.assertEqual(len(self.injury.treatment_note_ids), 1)
