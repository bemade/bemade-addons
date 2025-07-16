import logging
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from datetime import timedelta

_logger = logging.getLogger(__name__)


class TaskManagementPortal(CustomerPortal):
    """Controller for task management functionality in the portal"""
    
    def _check_access_to_task_model(self, model_name, record_id):
        """Verify the user has access to the record"""
        user = request.env.user
        record = request.env[model_name].browse(int(record_id))
        
        # Check if user is a treatment professional
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Check if record exists
        if not record.exists():
            raise UserError(_('Record not found.'))
            
        # For patient records, check team access
        if model_name == 'sports.patient':
            patient_id_int = int(record_id)
            accessible_teams = request.env['sports.team'].search([
                ('staff_ids.user_ids', '=', user.id),
                ('patient_ids', 'in', patient_id_int)
            ])
            
            if not accessible_teams and not is_treatment_prof:
                raise UserError(_('You do not have access to this patient.'))
                
        # For injury records, check team access through the patient
        elif model_name == 'sports.patient.injury':
            patient = record.patient_id
            team = record.team_id
            
            if team:
                is_team_staff = team.staff_ids.filtered(
                    lambda s: user.partner_id in s.user_ids.partner_id
                )
                
                if not is_team_staff and not is_treatment_prof:
                    raise UserError(_('You do not have access to this injury.'))
            else:
                raise UserError(_('This injury is not associated with a team.'))
        
        return record
    
    @http.route(['/my/activities'], type='http', auth='user', website=True)
    def view_activities(self, **kw):
        """Display list of activities assigned to the current user"""
        user = request.env.user
        partner = user.partner_id
        
        # Get all activities assigned to this user
        activities = request.env['mail.activity'].search([
            ('user_id', '=', user.id),
            ('res_model', 'in', ['sports.patient', 'sports.patient.injury']),
        ], order='date_deadline asc')
        
        # Group activities by model
        patient_activities = activities.filtered(lambda a: a.res_model == 'sports.patient')
        injury_activities = activities.filtered(lambda a: a.res_model == 'sports.patient.injury')
        
        # Get activity types for filtering
        activity_types = request.env['mail.activity.type'].search([])
        
        values = {
            'activities': activities,
            'patient_activities': patient_activities,
            'injury_activities': injury_activities,
            'activity_types': activity_types,
            'page_name': 'activities',
        }
        
        return request.render('bemade_sports_clinic.portal_my_activities', values)
    
    @http.route(['/my/activity/create'], type='http', auth='user', website=True)
    def create_activity_form(self, model=None, res_id=None, **kw):
        """Display form to create a new activity"""
        # Validate model and res_id
        valid_models = ['sports.patient', 'sports.patient.injury']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        try:
            record = self._check_access_to_task_model(model, res_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Get activity types
        activity_types = request.env['mail.activity.type'].search([])
        
        # Get users that can be assigned to activities
        domain = []
        
        # If this is an injury record, filter by team staff
        if model == 'sports.patient.injury':
            team = record.team_id
            if team:
                domain = [('partner_id', 'in', team.staff_ids.mapped('partner_id').ids)]
                
        # Only treatment professionals can see and assign all users
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            domain.append(('id', '=', request.env.user.id))
            
        assignable_users = request.env['res.users'].search(domain)
        
        # Prepare record name for display
        record_name = record.name if hasattr(record, 'name') else record.display_name
        
        # Default return URL
        if model == 'sports.patient':
            return_url = f'/my/player?player_id={res_id}'
        else:  # sports.patient.injury
            return_url = f'/my/player?player_id={record.patient_id.id}'
            
        values = {
            'activity_types': activity_types,
            'assignable_users': assignable_users,
            'record': record,
            'record_name': record_name,
            'model': model,
            'res_id': res_id,
            'default_user_id': request.env.user.id,
            'return_url': kw.get('return_url', return_url),
            'page_name': 'create_activity',
        }
        
        return request.render('bemade_sports_clinic.portal_create_activity', values)
    
    @http.route(['/my/activity/save'], type='http', auth='user', website=True, methods=['POST'])
    def create_activity_submit(self, **post):
        """Process form submission to create a new activity"""
        model = post.get('model')
        res_id = post.get('res_id')
        
        # Validate model and res_id
        valid_models = ['sports.patient', 'sports.patient.injury']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        try:
            record = self._check_access_to_task_model(model, res_id)
        except UserError as e:
            return request.render('portal.403', {'error': str(e)})
            
        # Validate required fields
        activity_type_id = post.get('activity_type_id')
        summary = post.get('summary')
        user_id = post.get('user_id')
        date_deadline = post.get('date_deadline')
        
        if not activity_type_id or not summary or not user_id or not date_deadline:
            return_url = post.get('return_url', '/my/activities')
            return request.redirect(f'{return_url}&error=missing_fields')
            
        # Check if the assigned user is valid
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        assigned_user = request.env['res.users'].browse(int(user_id))
        
        # Only treatment professionals can assign to other users
        if not is_treatment_prof and assigned_user.id != request.env.user.id:
            return_url = post.get('return_url', '/my/activities')
            return request.redirect(f'{return_url}&error=invalid_user')
            
        # Create the activity
        vals = {
            'activity_type_id': int(activity_type_id),
            'summary': summary,
            'note': post.get('note', ''),
            'user_id': int(user_id),
            'date_deadline': date_deadline,
            'res_model_id': request.env['ir.model']._get_id(model),
            'res_id': int(res_id),
        }
        
        activity = request.env['mail.activity'].sudo().create(vals)
        
        # Redirect to the return URL or activities page
        return_url = post.get('return_url', '/my/activities')
        return request.redirect(f'{return_url}&success=activity_created')
    
    @http.route(['/my/activity/complete'], type='http', auth='user', website=True, methods=['POST'])
    def complete_activity(self, activity_id, **post):
        """Mark an activity as done"""
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists and belongs to the current user
        if not activity.exists() or activity.user_id != request.env.user:
            return request.redirect('/my/activities')
            
        # Add feedback if provided
        feedback = post.get('feedback', '')
        
        # Mark the activity as done
        activity.sudo().action_feedback(feedback=feedback)
        
        # Redirect to activities page
        return request.redirect('/my/activities')
    
    @http.route(['/my/activity/cancel'], type='http', auth='user', website=True, methods=['POST'])
    def cancel_activity(self, activity_id, **post):
        """Cancel an activity"""
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists and belongs to the current user
        if not activity.exists() or activity.user_id != request.env.user:
            return request.redirect('/my/activities')
            
        # Cancel the activity
        activity.sudo().unlink()
        
        # Redirect to activities page
        return request.redirect('/my/activities')
    
    @http.route(['/my/activity/reschedule'], type='http', auth='user', website=True, methods=['POST'])
    def reschedule_activity(self, activity_id, **post):
        """Reschedule an activity to a new date"""
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists and belongs to the current user
        if not activity.exists() or activity.user_id != request.env.user:
            return request.redirect('/my/activities')
            
        # Get new deadline
        new_deadline = post.get('new_deadline')
        if not new_deadline:
            return request.redirect('/my/activities')
            
        # Update the deadline
        activity.sudo().write({'date_deadline': new_deadline})
        
        # Redirect to activities page
        return request.redirect('/my/activities')
