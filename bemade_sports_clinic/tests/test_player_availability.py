from odoo.tests import TransactionCase, tagged
from unittest import skip  # 19.0 coverage pass: quarantine drifted orphan tests
from odoo.exceptions import ValidationError


@tagged("-at_install", "post_install")
class TestPlayerAvailability(TransactionCase):
    """Tests for player match and practice availability functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a patient for testing
        cls.patient = cls.env["sports.patient"].create({
            "first_name": "Availability",
            "last_name": "Test",
            # These are the default values but we set them explicitly
            "match_status": "yes",
            "practice_status": "yes",
        })

    def test_default_availability_values(self):
        """Test that default values are set correctly"""
        self.assertEqual(self.patient.match_status, "yes", "Default match status should be 'yes'")
        self.assertEqual(self.patient.practice_status, "yes", "Default practice status should be 'yes'")
        
    def test_valid_availability_combinations(self):
        """Test valid combinations of match and practice status"""
        valid_combinations = [
            # match_status, practice_status
            ("yes", "yes"),     # Fully available
            ("no", "yes"),      # Practice only
            ("no", "no_contact"),  # Limited practice
            ("no", "no"),       # No availability
        ]
        
        for match_status, practice_status in valid_combinations:
            # This should not raise an exception
            self.patient.write({
                "match_status": match_status,
                "practice_status": practice_status,
            })
            self.assertEqual(self.patient.match_status, match_status)
            self.assertEqual(self.patient.practice_status, practice_status)
    
    def test_invalid_availability_combinations(self):
        """Test invalid combinations raise ValidationError"""
        invalid_combinations = [
            # match_status, practice_status
            ("yes", "no"),        # Can play matches but not practice
            ("yes", "no_contact"), # Can play matches but only limited practice
        ]
        
        for match_status, practice_status in invalid_combinations:
            with self.assertRaises(ValidationError, msg=f"Combination {match_status}, {practice_status} should be invalid"):
                self.patient.write({
                    "match_status": match_status,
                    "practice_status": practice_status,
                })
                
    def test_is_injured_computation(self):
        """Test that the is_injured field is computed correctly based on availability"""
        # Default status (yes, yes) - not injured
        self.assertFalse(self.patient.is_injured, "Player with full availability should not be marked as injured")
        
        # Change to no match, yes practice
        self.patient.write({
            "match_status": "no",
            "practice_status": "yes",
        })
        self.assertTrue(self.patient.is_injured, "Player with limited availability should be marked as injured")
        
        # Change to no match, no practice
        self.patient.write({
            "match_status": "no",
            "practice_status": "no",
        })
        self.assertTrue(self.patient.is_injured, "Player with no availability should be marked as injured")
        
        # Reset to full availability
        self.patient.write({
            "match_status": "yes",
            "practice_status": "yes",
        })
        self.assertFalse(self.patient.is_injured, "Player with restored availability should not be marked as injured")
        
    def test_stage_computation(self):
        """Test that the player stage is computed correctly based on availability"""
        # Full availability - healthy
        self.patient.write({
            "match_status": "yes",
            "practice_status": "yes",
        })
        self.assertEqual(self.patient.stage, "healthy", "Player with full availability should be in 'healthy' stage")
        
        # Practice only - practice_ok
        self.patient.write({
            "match_status": "no",
            "practice_status": "yes",
        })
        self.assertEqual(self.patient.stage, "practice_ok", "Player with practice only should be in 'practice_ok' stage")
        
        # Limited practice - practice_ok
        self.patient.write({
            "match_status": "no",
            "practice_status": "no_contact",
        })
        self.assertEqual(self.patient.stage, "practice_ok", "Player with limited practice should be in 'practice_ok' stage")
        
        # No availability - no_play
        self.patient.write({
            "match_status": "no",
            "practice_status": "no",
        })
        self.assertEqual(self.patient.stage, "no_play", "Player with no availability should be in 'no_play' stage")

    def test_availability_tracking(self):
        """Changing availability (match/practice status) is tracked in the chatter."""
        # Patients in practice have followers (treatment professionals / team);
        # subscribe one so the change posts a proper tracking-value entry.
        self.patient.message_subscribe(partner_ids=[self.env.user.partner_id.id])
        initial_message_count = len(self.patient.message_ids)

        # Real change: match_status defaults to 'yes'.
        self.patient.write({"match_status": "no"})

        # Odoo finalizes field tracking in a cr.precommit callback (runs at
        # commit). A TransactionCase never commits, so flush the write then run
        # the precommit callbacks explicitly, and re-read message_ids.
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.patient.invalidate_recordset(["message_ids"])

        # Changing availability must post a chatter entry. match_status is an
        # "external" tracked field, so at runtime it posts the patient
        # status-update notification (and a tracking-value row on commit). The
        # robust, runtime-independent check is that a chatter message is added.
        self.assertGreater(
            len(self.patient.message_ids), initial_message_count,
            "Changing availability should post a chatter message",
        )

    def test_availability_with_injury(self):
        """Test interaction between injuries and availability"""
        # Create an injury
        injury = self.env["sports.patient.injury"].create({
            "patient_id": self.patient.id,
            "diagnosis": "Test Injury",
            "injury_date": "2025-07-01",
        })
        
        # Set the patient as unavailable for matches
        self.patient.write({
            "match_status": "no",
            "practice_status": "no",
        })
        
        # Verify the patient is marked as injured
        self.assertTrue(self.patient.is_injured, "Patient should be injured with no availability")
        self.assertEqual(self.patient.stage, "no_play", "Patient should be in no_play stage")
        
        # Check that injured_since is set to the injury date
        self.assertEqual(self.patient.injured_since.strftime('%Y-%m-%d'), "2025-07-01", 
                         "injured_since should be set to the injury date")
