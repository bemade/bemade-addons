from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import timedelta


class TaskToEventWizard(models.TransientModel):
    _name = 'task.to.event.wizard'
    _description = 'Convert Project Tasks to Sports Events'

    task_ids = fields.Many2many(
        'project.task',
        string='Selected Tasks',
        required=True,
        help='Tasks to convert to sports events'
    )
    
    team_id = fields.Many2one(
        'sports.team',
        string='Team',
        required=True,
        help='Team to assign to all created events'
    )
    
    event_type = fields.Selection([
        ('game', 'Game'),
        ('practice', 'Practice'),
        ('training', 'Training'),
        ('meeting', 'Team Meeting'),
        ('other', 'Other')
    ], string='Event Type', default='other', required=True,
       help='Type of event for all created events')
    
    venue_id = fields.Many2one(
        'res.partner',
        string='Venue',
        domain=[('is_venue', '=', True)],
        help='Default venue for all events (can be changed individually later)'
    )
    
    task_count = fields.Integer(
        string='Number of Tasks',
        compute='_compute_task_count'
    )
    
    @api.depends('task_ids')
    def _compute_task_count(self):
        for wizard in self:
            wizard.task_count = len(wizard.task_ids)
    
    def _extract_venue_from_description(self, description):
        """Extract venue from task description and find or create venue"""
        import re
        
        # Look for "Location: " in the description (case insensitive)
        match = re.search(r'location:\s*(.+?)(?:\n|$)', description, re.IGNORECASE)
        if not match:
            return False
            
        venue_name = match.group(1).strip()
        if not venue_name:
            return False
            
        # Try to find existing venue by name
        existing_venue = self.env['res.partner'].search([
            ('name', '=', venue_name),
            ('is_venue', '=', True)
        ], limit=1)
        
        if existing_venue:
            return existing_venue.id
            
        # Create new venue if not found
        new_venue = self.env['res.partner'].create({
            'name': venue_name,
            'is_company': True,
            'is_venue': True,
            'supplier_rank': 0,
            'customer_rank': 0,
        })
        
        return new_venue.id
    
    @api.model
    def default_get(self, fields_list):
        """Set default task_ids from context"""
        res = super().default_get(fields_list)
        
        # Get selected tasks from context
        active_ids = self.env.context.get('active_ids', [])
        if active_ids and 'task_ids' in fields_list:
            res['task_ids'] = [(6, 0, active_ids)]
            
        return res
    
    def action_convert_tasks(self):
        """Convert selected tasks to sports events"""
        if not self.task_ids:
            raise UserError("No tasks selected for conversion.")
            
        if not self.team_id:
            raise UserError("Please select a team for the events.")
        
        # Ensure we have unique tasks (prevent duplicates)
        unique_tasks = self.task_ids.filtered(lambda t: t.id)
        if not unique_tasks:
            raise UserError("No valid tasks found for conversion.")
        
        # Check if any tasks have already been converted for THIS SPECIFIC TEAM
        # Allow the same task to be converted for different teams (overlapping events)
        existing_events = self.env['sports.event'].search([
            ('task_id', 'in', unique_tasks.ids),
            ('team_ids', 'in', [self.team_id.id])  # Only check for same team
        ])
        
        if existing_events:
            task_names = existing_events.mapped('task_id.name')
            raise UserError(f"Some tasks have already been converted for team '{self.team_id.name}': {', '.join(task_names)}. "
                          f"Each task can only be converted once per team.")
        
        created_events = self.env['sports.event']
        # Note: Removed processed_task_ids tracking since we now allow the same task 
        # to be converted multiple times for different teams
        
        for task in unique_tasks:
            
            # Validate task has required information
            if not task.name:
                raise UserError(f"Task {task.id} has no name and cannot be converted.")
            
            # Determine event dates from task planned dates
            date_start = task.planned_date_begin or task.date_deadline
            date_end = task.date_deadline
            
            if not date_start:
                raise UserError(f"Task '{task.name}' has no planned start date or deadline and cannot be converted.")
            
            # If no end date, set it to start date + 2 hours (reasonable default)
            if not date_end:
                from datetime import timedelta
                date_end = date_start + timedelta(hours=2)
            
            # Ensure end date is after start date
            if date_end <= date_start:
                from datetime import timedelta
                date_end = date_start + timedelta(hours=2)
            
            # Extract venue from task description if available
            venue_id = self.venue_id.id if self.venue_id else False
            if task.description and not venue_id:
                venue_id = self._extract_venue_from_description(task.description)
            
            # Create the sports event
            event_vals = {
                'name': task.name,
                'description': task.description or '',
                'date_start': date_start,
                'date_end': date_end,
                'therapist_start': date_start,  # Therapist start = event start
                'therapist_end': date_end,      # Therapist end = event end
                'team_ids': [(6, 0, [self.team_id.id])],
                'event_type': self.event_type,
                'venue_id': venue_id,
                'task_id': task.id,  # Link back to original task
                'project_id': task.project_id.id if task.project_id else False,
                'state': 'confirmed',
            }
            
            # Set assigned staff from task users, restricted to treatment professionals
            # (internal or portal). Coaches and other roles are excluded — assigned_staff_ids
            # represents who provides medical/therapy coverage at the event.
            if task.user_ids:
                tp_internal = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional', raise_if_not_found=False)
                tp_portal = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional', raise_if_not_found=False)
                tp_group_ids = [g.id for g in (tp_internal, tp_portal) if g]
                if tp_group_ids:
                    tp_users = task.user_ids.filtered(lambda u: any(g.id in tp_group_ids for g in u.groups_id))
                    if tp_users:
                        event_vals['assigned_staff_ids'] = [(6, 0, tp_users.ids)]
            
            event = self.env['sports.event'].create(event_vals)
            created_events |= event
            
            # Add a note to the task about the conversion (without sending emails)
            task.with_context(mail_notrack=True, mail_create_nolog=True).message_post(
                body=f"Task converted to Sports Event for team '{self.team_id.name}': <a href='/web#id={event.id}&model=sports.event'>{event.name}</a>",
                subject=f"Converted to Sports Event ({self.team_id.name})"
            )
        
        # Return action to view created events
        if len(created_events) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Sports Event',
                'res_model': 'sports.event',
                'res_id': created_events.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Sports Events',
                'res_model': 'sports.event',
                'view_mode': 'list,form',
                'domain': [('id', 'in', created_events.ids)],
                'target': 'current',
            }
