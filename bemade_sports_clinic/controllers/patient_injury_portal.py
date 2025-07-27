import logging
import base64
import io
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from datetime import datetime

_logger = logging.getLogger(__name__)


class PatientInjuryPortal(CustomerPortal):
    """Controller for all injury reporting functionality in the portal"""
    
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
        # Use request.env.user.has_group() directly to avoid security violations
        is_medical = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        if not patient.exists() or (not accessible_teams and not is_medical):
            raise UserError(_('You do not have access to this patient.'))
            
        return patient
    
    @http.route(['/my/patient/injury/new'], type='http', auth='user', website=True)
    def create_injury_form(self, patient_id=None, **post):
        """Show form to create a new injury report"""
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        return_url = post.get('return_url', f'/my/player?player_id={patient_id}')
        
        # Check if user is a treatment professional
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        values = {
            'patient': patient,
            'return_url': return_url,
            'page_name': 'report_injury',
            'is_treatment_prof': is_treatment_prof,  # Pass flag to template for conditional display
        }
        
        return request.render('bemade_sports_clinic.portal_create_injury', values)
    
    @http.route(['/my/patient/injury/create'], type='http', auth='user', website=True, methods=['POST'])
    def create_injury_submit(self, **post):
        """Process the form submission to create a new injury"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Since team_id is no longer in the portal form, we'll use the patient's first team
        # or None if the patient has multiple teams (let the model handle assignment)
        patient_teams = patient.team_ids
        team_id = patient_teams[0].id if len(patient_teams) == 1 else None
            
        # Check if the current user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Prepare values for injury creation
        vals = {
            'patient_id': patient.id,
            'diagnosis': post.get('diagnosis', ''),
            'injury_date': post.get('injury_date'),
            'external_notes': post.get('external_notes', ''),
            'stage': 'active' if is_treatment_prof else 'unverified',
        }
        
        # Only add team_id if we have a single team for the patient
        if team_id:
            vals['team_id'] = int(team_id)
        
        # Handle optional fields
        if post.get('parental_consent'):
            vals['parental_consent'] = post.get('parental_consent')
        
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
            
        # Create the injury record - portal users now have create permission
        injury = request.env['sports.patient.injury'].create(vals)
        
        # Determine if user is a coach or treatment professional
        # Use request.env.user.has_group() directly to avoid security violations
        is_portal_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Detailed logging of the current user's status
        _logger.info(f"Current user: {user.name} (ID: {user.id})")
        _logger.info(f"Is portal coach: {is_portal_coach}")
        _logger.info(f"Is in treatment professional group: {is_treatment_prof}")
        
        # If user is a treatment professional, add them to the treatment professionals
        # Only check group membership, not computed field
        if is_treatment_prof:
            _logger.info(f"Adding current user {user.name} (ID: {user.id}) to treatment professionals")
            injury.write({
                'treatment_professional_ids': [(4, user.id)]
            })
        else:
            _logger.info(f"User {user.name} is not identified as a treatment professional, not adding to injury")
        
        # Double-check who's assigned after our additions
        treatment_profs = injury.treatment_professional_ids
        _logger.info(f"Treatment professionals after assignment: {[u.name for u in treatment_profs]} (IDs: {treatment_profs.ids})")

        # Always try to assign team therapists regardless of who created the injury
        if True:
            # Use the selected team_id from the form
            selected_team_id = int(team_id)
            
            # Find therapists specifically for this team
            team_staff = request.env['sports.team.staff'].sudo().search([
                ('team_id', '=', selected_team_id),  # Only from selected team
                ('role', 'in', ['head_therapist', 'therapist'])
            ])
            
            # Log debug info
            _logger.info(f"Found {len(team_staff)} therapists/head therapists for team {selected_team_id}")
            for staff in team_staff:
                _logger.info(f"Staff: {staff.partner_id.name}, Role: {staff.role}, User IDs: {[u.id for u in staff.user_ids]}")
                if not staff.user_ids:
                    _logger.info(f"  - WARNING: No user_ids for {staff.partner_id.name}")
                    # Try to find a user directly associated with this partner
                    users = request.env['res.users'].sudo().search([('partner_id', '=', staff.partner_id.id)])
                    _logger.info(f"  - Found direct users: {[u.id for u in users]}")
            
            # Filter by role
            head_therapists = team_staff.filtered(lambda s: s.role == 'head_therapist')
            therapists = team_staff.filtered(lambda s: s.role == 'therapist')
            
            _logger.info(f"Found {len(head_therapists)} head therapists and {len(therapists)} therapists")
            
            # First try to assign head therapist, then any therapist from the selected team
            treatment_pros_assigned = False
            
            # Try to assign head therapist first
            if head_therapists:
                # Find users associated directly with the head therapist partner
                head_therapist = head_therapists[0]
                users = request.env['res.users'].search([('partner_id', '=', head_therapist.partner_id.id)])
                
                if users:
                    _logger.info(f"Assigning head therapist: {head_therapist.partner_id.name} with user ID {users[0].id}")
                    injury.write({
                        'treatment_professional_ids': [(4, users[0].id)]
                    })
                    treatment_pros_assigned = True
                else:
                    _logger.info(f"No user account found for head therapist: {head_therapist.partner_id.name}")
            
            # Try to assign regular therapist if no head therapist was assigned
            if not treatment_pros_assigned and therapists:
                # Find users associated directly with the therapist partner
                therapist = therapists[0]
                users = request.env['res.users'].sudo().search([('partner_id', '=', therapist.partner_id.id)])
                
                if users:
                    _logger.info(f"Assigning therapist: {therapist.partner_id.name} with user ID {users[0].id}")
                    injury.write({
                        'treatment_professional_ids': [(4, users[0].id)]
                    })
                    treatment_pros_assigned = True
                else:
                    _logger.info(f"No user account found for therapist: {therapist.partner_id.name}")
            
            # If no therapist was assigned, log a warning
            if not treatment_pros_assigned:
                _logger.warning("No valid therapists found to assign to the injury")
            
        # Trigger recomputation of patient status based on the injury
        patient._compute_is_injured()
        patient._compute_stage()
        
        return_url = f'/my/player?player_id={patient_id}'
        values = {
            'return_url': return_url,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_created', values)
        
    def _check_access_to_injury(self, injury_id):
        """Verify the user has access to this injury"""
        user = request.env.user
        injury = request.env['sports.patient.injury'].browse(int(injury_id))
        
        # Check if user has access to this injury based on patient's team ownership
        if not injury.exists():
            raise UserError(_('Injury not found.'))
            
        # Get the patient's teams
        patient_teams = injury.patient_id.team_ids
        
        if patient_teams:
            # Check if user is part of any of the patient's team staff
            user_teams = request.env['sports.team.staff'].search([
                ('team_id', 'in', patient_teams.ids),
                ('user_ids', '=', user.id)
            ])
            
            # Medical professionals might have specific access
            # Use request.env.user.has_group() directly to avoid security violations
            is_medical = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            
            if not user_teams and not is_medical:
                raise UserError(_('You do not have access to this injury.'))
        else:
            # If patient has no teams, only medical professionals can access
            # Use request.env.user.has_group() directly to avoid security violations
            if not request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional'):
                raise UserError(_('You do not have access to this injury.'))
                
        return injury
        
    @http.route(['/my/injury/edit'], type='http', auth='user', website=True)
    def edit_injury_form(self, injury_id=None, **post):
        """Show form to edit an existing injury"""
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        return_url = post.get('return_url', f'/my/player?player_id={injury.patient_id.id}')
        
        # Get possible injury stages - treatment professionals can change stage
        stages = []
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        if is_treatment_prof:
            stage_selection = request.env['sports.patient.injury']._fields['stage'].selection
            stages = [(k, v) for k, v in stage_selection]
        
        # Get treatment professionals for the multi-select field
        treatment_professionals = request.env['res.users'].search([
            ('groups_id', 'in', request.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id)
        ])
        
        # Get parental consent options if treatment professional
        parental_consent_options = None
        if is_treatment_prof:
            parental_consent_options = request.env['sports.patient.injury']._fields['parental_consent'].selection
            
        values = {
            'injury': injury,
            'stages': stages,
            'treatment_professionals': treatment_professionals,
            'parental_consent_options': parental_consent_options,
            'return_url': return_url,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'edit_injury',
            'error': post.get('error'),
            'success': post.get('success'),
        }
        
        return request.render('bemade_sports_clinic.portal_edit_injury', values)
        
    @http.route(['/my/injury/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_injury_submit(self, **post):
        """Process the form submission to update an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Get user's role
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Prepare values for injury update
        vals = {}
        
        # Fields everyone can update
        vals.update({
            'diagnosis': post.get('diagnosis', injury.diagnosis or ''),
            'external_notes': post.get('external_notes', injury.external_notes or ''),
        })
        
        # Handle injury date and N/A checkbox
        if post.get('injury_date_na'):
            vals['injury_date_na'] = True
            vals['injury_date'] = False  # Clear the date if N/A is checked
        else:
            vals['injury_date_na'] = False
            if post.get('injury_date'):
                vals['injury_date'] = post.get('injury_date')
        

        
        # Handle resolution dates
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
        
        if post.get('resolution_date'):
            vals['resolution_date'] = post.get('resolution_date')
        
        # Handle treatment professionals (multi-select)
        if post.get('treatment_professional_ids'):
            # Convert to list if it's a single value
            prof_ids = post.get('treatment_professional_ids')
            if isinstance(prof_ids, str):
                prof_ids = [prof_ids]
            elif not isinstance(prof_ids, list):
                prof_ids = [prof_ids]
            
            # Convert to integers and set using Odoo's many2many syntax
            prof_ids = [int(pid) for pid in prof_ids if pid]
            vals['treatment_professional_ids'] = [(6, 0, prof_ids)]
        
        # Fields only treatment professionals can update
        if is_treatment_prof:
            if post.get('internal_notes'):
                vals['internal_notes'] = post.get('internal_notes')
                
            if post.get('stage'):
                vals['stage'] = post.get('stage')
                
            if post.get('parental_consent'):
                vals['parental_consent'] = post.get('parental_consent')
                
        # Update the injury
        injury.sudo().write(vals)
        
        # Add a treatment note if provided
        if post.get('treatment_note') and is_treatment_prof:
            _logger.info(f"DEBUG: About to create treatment note for injury {injury.id}")
            _logger.info(f"DEBUG: injury.patient_id = {injury.patient_id} (ID: {injury.patient_id.id})")
            _logger.info(f"DEBUG: injury.patient_id.partner_id = {injury.patient_id.partner_id} (ID: {injury.patient_id.partner_id.id if injury.patient_id.partner_id else 'None'})")
            self._add_treatment_note(injury.patient_id, post.get('treatment_note'), injury)
        
        # Redirect back to the edit form with success message
        return_url = post.get('return_url', f'/my/injury/edit?injury_id={injury_id}')
        return request.redirect(f'{return_url}&success=injury_updated')
        
    def _add_treatment_note(self, patient, note_content, injury=None):
        """Helper method to add a treatment note to a patient, optionally linked to an injury"""
        if not note_content.strip():
            return False
        
        _logger.info(f"DEBUG: _add_treatment_note called with patient={patient} (ID: {patient.id})")
        _logger.info(f"DEBUG: patient model: {patient._name}")
        if hasattr(patient, 'partner_id'):
            _logger.info(f"DEBUG: patient.partner_id = {patient.partner_id} (ID: {patient.partner_id.id if patient.partner_id else 'None'})")
            
        # Create a new treatment note linked to patient, optionally to injury
        vals = {
            'patient_id': patient.id,
            'note': note_content,
            'date': fields.Date.today(),
            'user_id': request.env.user.id,
        }
        _logger.info(f"DEBUG: About to create treatment note with vals: {vals}")
        
        # If injury is provided, link the note to it
        if injury:
            vals['injury_id'] = injury.id
            
        request.env['sports.treatment.note'].sudo().create(vals)
        
        return True
        
    @http.route(['/my/injury/notes'], type='http', auth='user', website=True)
    def view_treatment_notes(self, injury_id=None, patient_id=None, **post):
        """View treatment notes for an injury or a patient"""
        # Determine context - are we viewing injury-specific notes or all patient notes?
        # At least one of injury_id or patient_id must be provided
        if not injury_id and not patient_id:
            return request.redirect('/my/players')
            
        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        if injury_id:
            # Injury context
            try:
                injury = self._check_access_to_injury(injury_id)
                patient = injury.patient_id
            except UserError as e:
                return request.render('http_routing.http_error', {
                    'status_code': 403, 
                    'status_message': 'Forbidden',
                    'error_message': str(e)
                })
                
            # Get notes for this injury
            notes = request.env['sports.treatment.note'].sudo().search(
                [('injury_id', '=', int(injury_id))],
                order='date desc, id desc'
            )
            
            values = {
                'injury': injury,
                'notes': notes,
                'patient': patient,
                'is_treatment_prof': is_treatment_prof,
                'page_name': 'injury_notes',
                'error': post.get('error'),
                'success': post.get('success'),
                'context': 'injury',
            }
            
        else:
            # Patient context
            try:
                patient = self._check_access_to_patient(patient_id)
            except UserError as e:
                return request.render('http_routing.http_error', {
                    'status_code': 403, 
                    'status_message': 'Forbidden',
                    'error_message': str(e)
                })
                
            # Get all notes for this patient
            notes = request.env['sports.treatment.note'].sudo().search(
                [('patient_id', '=', int(patient_id))],
                order='date desc, id desc'
            )
            
            values = {
                'injury': None,
                'notes': notes,
                'patient': patient,
                'is_treatment_prof': is_treatment_prof,
                'page_name': 'patient_notes',
                'error': post.get('error'),
                'success': post.get('success'),
                'context': 'patient',
            }
            
        return request.render('bemade_sports_clinic.portal_treatment_notes', values)
        
    @http.route(['/my/injury/note/add'], type='http', auth='user', website=True, methods=['POST'])
    def add_treatment_note(self, **post):
        """Add a new treatment note to a patient, optionally linked to an injury"""
        # Get context - are we adding a note to an injury or just to a patient?
        injury_id = post.get('injury_id')
        patient_id = post.get('patient_id')
        
        # Either injury_id or patient_id must be provided
        if not injury_id and not patient_id:
            return request.redirect('/my/players')
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            # Determine redirect URL based on context
            if injury_id:
                return request.redirect(f'/my/injury/notes?injury_id={injury_id}&error=permission_denied')
            else:
                return request.redirect(f'/my/injury/notes?patient_id={patient_id}&error=permission_denied')
        
        # Get note content and validate
        note_content = post.get('note')
        if not note_content or not note_content.strip():
            if injury_id:
                return request.redirect(f'/my/injury/notes?injury_id={injury_id}&error=empty_note')
            else:
                return request.redirect(f'/my/injury/notes?patient_id={patient_id}&error=empty_note')
        
        # Determine context and add the note
        if injury_id:
            # Injury context
            try:
                injury = self._check_access_to_injury(injury_id)
                patient = injury.patient_id
                self._add_treatment_note(patient, note_content, injury)
                return request.redirect(f'/my/injury/notes?injury_id={injury_id}&success=note_added')
            except UserError as e:
                return request.render('http_routing.http_error', {
                    'status_code': 403, 
                    'status_message': 'Forbidden',
                    'error_message': str(e)
                })
        else:
            # Patient context
            try:
                patient = self._check_access_to_patient(patient_id)
            except UserError as e:
                return request.render('http_routing.http_error', {
                    'status_code': 403, 
                    'status_message': 'Forbidden',
                    'error_message': str(e)
                })
                
            self._add_treatment_note(patient, note_content)
            return request.redirect(f'/my/injury/notes?patient_id={patient_id}&success=note_added')
        
    @http.route(['/my/injury/documents'], type='http', auth='user', website=True)
    def view_injury_documents(self, injury_id=None, **post):
        """View documents attached to an injury"""
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Get documents for this injury
        documents = request.env['sports.injury.document'].sudo().search(
            [('injury_id', '=', int(injury_id))],
            order='create_date desc'
        )
        
        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Document categories
        categories = [('medical', 'Medical'), ('xray', 'X-Ray'), ('mri', 'MRI'), 
                      ('prescription', 'Prescription'), ('other', 'Other')]
        
        values = {
            'injury': injury,
            'documents': documents,
            'patient': injury.patient_id,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'injury_documents',
            'error': post.get('error'),
            'success': post.get('success'),
            'categories': categories,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_documents', values)
        
    @http.route(['/my/injury/document/upload'], type='http', auth='user', website=True, methods=['POST'])
    def upload_injury_document(self, **post):
        """Upload a document for an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Check if file was uploaded
        attachment = post.get('attachment')
        if not attachment:
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=no_file')
            
        # Process the file
        try:
            name = attachment.filename
            file_content = attachment.read()
            file_size = len(file_content)
            
            # Check file size (limit to 10MB)
            if file_size > 10 * 1024 * 1024:  # 10MB in bytes
                return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=file_too_large')
                
            # Create the document
            document = request.env['sports.injury.document'].sudo().create({
                'injury_id': int(injury_id),
                'name': post.get('document_name', name),
                'description': post.get('description', ''),
                'category': post.get('category', 'other'),
                'file_content': base64.b64encode(file_content),
                'file_name': name,
                'created_by_id': request.env.user.id,
            })
            
            # Redirect back to documents page with success message
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&success=document_uploaded')
            
        except Exception as e:
            _logger.error(f"Error uploading document: {e}")
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=upload_failed')
            
    @http.route(['/my/injury/document/download/<int:document_id>'], type='http', auth='user')
    def download_injury_document(self, document_id, **post):
        """Download a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Check access to the injury this document belongs to
            injury = self._check_access_to_injury(document.injury_id.id)
        except UserError:
            raise request.not_found()
            
        # Return the file for download
        return request.make_response(
            base64.b64decode(document.file_content),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{document.file_name}"'),
            ]
        )
        
    @http.route(['/my/injury/document/delete/<int:document_id>'], type='http', auth='user', website=True)
    def delete_injury_document(self, document_id, **post):
        """Delete a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Check access to the injury this document belongs to
            injury = self._check_access_to_injury(document.injury_id.id)
        except UserError:
            raise request.not_found()
            
        # Check if user is a treatment professional (only they can delete documents)
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return request.redirect(f'/my/injury/documents?injury_id={document.injury_id.id}&error=permission_denied')
            
        # Delete the document
        injury_id = document.injury_id.id
        document.sudo().unlink()
        
        # Redirect back to documents page with success message
        return request.redirect(f'/my/injury/documents?injury_id={injury_id}&success=document_deleted')
        
    @http.route(['/my/injury/verify'], type='http', auth='user', website=True, methods=['POST'])
    def verify_injury(self, injury_id, **post):
        """Verify an injury (change status from unverified to active)"""
        try:
            injury = request.env['sports.patient.injury'].browse(int(injury_id))
            
            # Check access - user must be a treatment professional or admin
            if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or 
                   request.env.user.has_group('base.group_system')):
                return request.redirect('/my')
                
            # Verify the injury
            injury.action_verify_injury()
            
            # Redirect back to the player page
            return request.redirect(f'/my/player?player_id={injury.patient_id.id}')
            
        except Exception as e:
            _logger.error(f"Error verifying injury: {e}")
            return request.redirect('/my')
