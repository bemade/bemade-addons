#!/usr/bin/env python3

from odoo.tests.common import TransactionCase
from odoo import fields
import logging

_logger = logging.getLogger(__name__)

class TestMailMessageDebug(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create test data similar to the failing test
        self.therapist_user = self.env['res.users'].create({
            'name': 'Test Therapist',
            'login': 'therapist@test.com',
            'email': 'therapist@test.com',
            'groups_id': [(6, 0, [self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id])]
        })
        
        # Create team and add therapist as staff
        self.team = self.env['sports.team'].create({
            'name': 'Test Team',
            'sport': 'football',
        })
        
        self.env['sports.team.staff'].create({
            'team_id': self.team.id,
            'partner_id': self.therapist_user.partner_id.id,
            'role': 'therapist',
        })
        
        # Create authorized patient
        self.authorized_patient = self.env['sports.patient'].create({
            'first_name': 'John',
            'last_name': 'Doe',
            'team_ids': [(6, 0, [self.team.id])],
        })
        
        # Create activity type
        self.patient_activity_type = self.env['mail.activity.type'].create({
            'name': 'Patient Activity',
            'res_model_id': self.env['ir.model']._get_id('sports.patient'),
        })

    def test_debug_mail_message_access(self):
        """Debug test to understand mail.message access control"""
        
        _logger.info("=== DEBUGGING MAIL.MESSAGE ACCESS ===")
        
        # Step 1: Create activity and complete it to generate message
        _logger.info("Step 1: Creating and completing activity...")
        activity = self.env['mail.activity'].create({
            'activity_type_id': self.patient_activity_type.id,
            'summary': 'Test activity for messages',
            'user_id': self.therapist_user.id,
            'date_deadline': fields.Date.today(),
            'res_model_id': self.env['ir.model']._get_id('sports.patient'),
            'res_id': self.authorized_patient.id,
        })
        
        # Complete activity to generate message
        activity.action_feedback(feedback='Activity completed successfully')
        
        # Step 2: Check if message was created
        _logger.info("Step 2: Checking if message was created...")
        all_messages = self.env['mail.message'].sudo().search([
            ('model', '=', 'sports.patient'),
            ('res_id', '=', self.authorized_patient.id)
        ])
        _logger.info(f"Found {len(all_messages)} messages for patient {self.authorized_patient.id}")
        
        if all_messages:
            message = all_messages[0]
            _logger.info(f"Message details: ID={message.id}, model={message.model}, res_id={message.res_id}, author_id={message.author_id.id}")
        
        # Step 3: Test patient access as therapist
        _logger.info("Step 3: Testing patient access as therapist...")
        patient_env = self.env['sports.patient'].with_user(self.therapist_user)
        accessible_patients = patient_env.search([('id', '=', self.authorized_patient.id)])
        _logger.info(f"Therapist can access {len(accessible_patients)} patients (should be 1)")
        
        if accessible_patients:
            _logger.info(f"Patient accessible: {accessible_patients[0].name}")
        else:
            _logger.error("PROBLEM: Therapist cannot access authorized patient!")
        
        # Step 4: Test message access as therapist using different methods
        _logger.info("Step 4: Testing message access as therapist...")
        message_env = self.env['mail.message'].with_user(self.therapist_user)
        
        # Method 1: Direct search
        messages_direct = message_env.search([
            ('model', '=', 'sports.patient'),
            ('res_id', '=', self.authorized_patient.id)
        ])
        _logger.info(f"Direct search found {len(messages_direct)} messages")
        
        # Method 2: Browse specific message ID
        if all_messages:
            message_browse = message_env.browse(all_messages[0].id)
            _logger.info(f"Browse message exists: {message_browse.exists()}")
            
            # Method 3: Check access manually
            try:
                message_browse.check_access('read')
                _logger.info("Manual check_access('read') passed")
            except Exception as e:
                _logger.error(f"Manual check_access('read') failed: {e}")
        
        # Step 5: Debug record rule evaluation
        _logger.info("Step 5: Debugging record rule evaluation...")
        
        # Check team staff relationships
        team_staff_rels = self.therapist_user.partner_id.team_staff_rel_ids
        _logger.info(f"Therapist has {len(team_staff_rels)} team staff relationships")
        
        if team_staff_rels:
            team_ids = team_staff_rels.mapped('team_id')
            _logger.info(f"Therapist is staff on teams: {team_ids.mapped('name')}")
            
            patient_ids = team_staff_rels.mapped('team_id.patient_ids.id')
            _logger.info(f"Accessible patient IDs through teams: {patient_ids}")
            
            # Check if our patient is in the list
            if self.authorized_patient.id in patient_ids:
                _logger.info("✓ Authorized patient is in accessible patient list")
            else:
                _logger.error("✗ Authorized patient is NOT in accessible patient list")
        
        # Step 6: Test mail.message record rule domain manually
        _logger.info("Step 6: Testing mail.message record rule domain manually...")
        
        # Simulate the record rule domain
        domain = [
            '|',
            # Messages on patients they have access to through teams
            '&',
            ('model', '=', 'sports.patient'),
            ('res_id', 'in', self.therapist_user.partner_id.team_staff_rel_ids.mapped('team_id.patient_ids.id') or [0]),
            '|',
            # Messages on injuries they have access to through teams
            '&',
            ('model', '=', 'sports.patient.injury'),
            ('res_id', 'in', self.therapist_user.partner_id.team_staff_rel_ids.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            # Messages authored by the user
            ('author_id', '=', self.therapist_user.partner_id.id)
        ]
        
        manual_messages = message_env.search(domain)
        _logger.info(f"Manual domain search found {len(manual_messages)} messages")
        
        _logger.info("=== END DEBUG ===")
        
        # Final assertion to see what happens
        self.assertTrue(len(messages_direct) > 0, "Should find messages with direct search")
