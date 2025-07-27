import logging
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager

_logger = logging.getLogger(__name__)


class PlayerManagementPortal(CustomerPortal):
    """Controller for player management functionality in the portal"""
    
    def _check_access_to_patient(self, patient_id):
        """Verify the user has access to this patient"""
        user = request.env.user
        patient = request.env['sports.patient'].browse(int(patient_id))
        
        # Check if user has access to any team this patient belongs to
        patient_id_int = int(patient_id)
        accessible_teams = request.env['sports.team'].search([
            ('staff_ids.user_ids', '=', user.id),
            ('patient_ids', 'in', patient_id_int)
        ])
        
        # Medical professionals might have specific access
        is_medical = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        if not patient.exists() or (not accessible_teams and not is_medical):
            raise UserError(_('You do not have access to this patient.'))
            
        return patient
    
    @http.route(['/my/player/edit'], type='http', auth='user', website=True)
    def edit_player_form(self, patient_id, **post):
        """Show form to edit player information"""
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        return_url = post.get('return_url', f'/my/player?player_id={patient_id}')
        
        # Check if user is a treatment professional
        user = request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        teams = patient.team_ids
        
        # Create a dictionary with patient info for protected fields
        patient_info = {}
        
        # Only include protected fields if user has appropriate permissions
        if is_treatment_prof:
            # Access fields directly - field-level security is already defined
            # with appropriate groups for each field
            
            # Debug log to check fields
            _logger = logging.getLogger(__name__)
            _logger.info(f"DEBUG - Allergies: {patient.allergies}")
            _logger.info(f"DEBUG - Team Info Notes: {patient.team_info_notes}")
            
            # Basic fields
            patient_info['date_of_birth'] = patient.date_of_birth
            patient_info['age'] = patient.age
            patient_info['allergies'] = patient.allergies
            patient_info['team_info_notes'] = patient.team_info_notes
            
            # Status fields
            patient_info['match_status'] = patient.match_status
            patient_info['practice_status'] = patient.practice_status
            
            # Injury tracking fields
            patient_info['injured_since'] = patient.injured_since
            
            # Add any other protected fields that should be available to treatment professionals
            # You can add more fields here as needed
            
            # Debug log for the entire patient_info dictionary
            _logger.info(f"DEBUG - patient_info: {patient_info}")
        
        values = {
            'patient': patient,  # Keep original patient
            'patient_info': patient_info,  # Add patient_info for protected fields
            'teams': teams,
            'return_url': return_url,
            'page_name': 'edit_player',
            'is_treatment_prof': is_treatment_prof,
        }
        
        return request.render('bemade_sports_clinic.portal_edit_player', values)
    
    @http.route(['/my/player/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_player_submit(self, **post):
        """Process the form submission to update player information"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Prepare values for patient update
        vals = {}
        
        # Basic information - any portal user with access can update these
        if post.get('first_name') and post.get('last_name'):
            vals.update({
                'first_name': post.get('first_name'),
                'last_name': post.get('last_name'),
            })
            
        # Contact information
        if post.get('email'):
            vals.update({
                'email': post.get('email'),
            })
            
        if post.get('phone'):
            vals.update({
                'phone': post.get('phone'),
            })
            
        # Additional fields that only treatment professionals can update
        if is_treatment_prof:
            if post.get('date_of_birth'):
                vals.update({
                    'date_of_birth': post.get('date_of_birth'),
                })
                
            # Medical information
            if 'allergies' in post:
                vals.update({
                    'allergies': post.get('allergies') or False,
                })
                
            if 'team_info_notes' in post:
                vals.update({
                    'team_info_notes': post.get('team_info_notes') or False,
                })
                
            # Status fields
            if post.get('match_status'):
                vals.update({
                    'match_status': post.get('match_status'),
                })
                
            if post.get('practice_status'):
                vals.update({
                    'practice_status': post.get('practice_status'),
                })
        
        # Update the patient - no sudo needed as field-level security is in place
        if vals:
            patient.write(vals)
        
        return request.redirect(f'/my/player?player_id={patient_id}')
    
    @http.route(['/my/player/contact/add'], type='http', auth='user', website=True)
    def add_contact_form(self, patient_id, **post):
        """Show form to add a new emergency contact for a player"""
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        return_url = post.get('return_url', f'/my/player?player_id={patient_id}')
        
        # Check if user is a treatment professional
        user = request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Regular coaches shouldn't be able to add emergency contacts
        if not is_treatment_prof:
            return request.redirect(return_url)
        
        values = {
            'patient': patient,
            'return_url': return_url,
            'page_name': 'add_contact',
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
        }
        
        return request.render('bemade_sports_clinic.portal_add_contact', values)
    
    @http.route(['/my/player/contact/save'], type='http', auth='user', website=True, methods=['POST'])
    def add_contact_submit(self, **post):
        """Process the form submission to add a new emergency contact"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Regular coaches shouldn't be able to add emergency contacts
        if not is_treatment_prof:
            return request.redirect(f'/my/player?player_id={patient_id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            values = {
                'patient': patient,
                'error': _("Name and contact type are required fields"),
                'return_url': f'/my/player?player_id={patient_id}',
                'page_name': 'add_contact',
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            }
            values.update(post)
            return request.render('bemade_sports_clinic.portal_add_contact', values)
        
        # Prepare values for contact creation
        vals = {
            'patient_id': int(patient_id),
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        if post.get('email'):
            vals['email'] = post.get('email')
        
        # Create the contact
        request.env['sports.patient.contact'].sudo().create(vals)
        
        return request.redirect(f'/my/player?player_id={patient_id}')
    
    @http.route(['/my/player/contact/edit'], type='http', auth='user', website=True)
    def edit_contact_form(self, contact_id, **post):
        """Show form to edit an existing emergency contact"""
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        return_url = post.get('return_url', f'/my/player?player_id={patient.id}')
        
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Regular coaches shouldn't be able to edit emergency contacts
        if not is_treatment_prof:
            return request.redirect(return_url)
        
        values = {
            'patient': patient,
            'contact': contact,
            'return_url': return_url,
            'page_name': 'edit_contact',
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
        }
        
        return request.render('bemade_sports_clinic.portal_edit_contact', values)
    
    @http.route(['/my/player/contact/update'], type='http', auth='user', website=True, methods=['POST'])
    def edit_contact_submit(self, **post):
        """Process the form submission to update an emergency contact"""
        contact_id = post.get('contact_id')
        
        if not contact_id:
            return request.redirect('/my/players')
            
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Regular coaches shouldn't be able to edit emergency contacts
        if not is_treatment_prof:
            return request.redirect(f'/my/player?player_id={patient.id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            values = {
                'patient': patient,
                'contact': contact,
                'error': _("Name and contact type are required fields"),
                'return_url': f'/my/player?player_id={patient.id}',
                'page_name': 'edit_contact',
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            }
            values.update(post)
            return request.render('bemade_sports_clinic.portal_edit_contact', values)
        
        # Prepare values for contact update
        vals = {
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        else:
            vals['mobile'] = False
        
        if post.get('email'):
            vals['email'] = post.get('email')
        else:
            vals['email'] = False
        
        # Update the contact
        contact.sudo().write(vals)
        
        return request.redirect(f'/my/player?player_id={patient.id}')
    
    @http.route(['/my/player/contact/delete'], type='http', auth='user', website=True, methods=['POST'])
    def delete_contact(self, contact_id, **post):
        """Delete an emergency contact"""
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Regular coaches shouldn't be able to delete emergency contacts
        if not is_treatment_prof:
            return request.redirect(f'/my/player?player_id={patient.id}')
        
        # Delete the contact
        contact.sudo().unlink()
        
        return request.redirect(f'/my/player?player_id={patient.id}')
