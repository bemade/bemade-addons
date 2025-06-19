# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    # Add a computed field to easily access the employee
    employee_id = fields.Many2one(
        'hr.employee', 
        string='Related Employee',
        compute='_compute_employee_id',
        store=True,
        help="Employee linked to this user"
    )
    
    employee_ids = fields.One2many(
        'hr.employee', 
        'portal_user_id',
        string='Portal Employees',
        help="Employees linked to this portal user"
    )
    
    @api.depends('employee_ids', 'groups_id')
    def _compute_employee_id(self):
        """Compute the related employee for this user."""
        for user in self:
            # First check if there's an employee with this user as portal_user_id
            if user.employee_ids:
                user.employee_id = user.employee_ids[0]
            else:
                # Then check if there's an employee with this user as user_id
                employee = self.env['hr.employee'].sudo().search([
                    ('user_id', '=', user.id)
                ], limit=1)
                user.employee_id = employee.id if employee else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle employee synchronization."""
        users = super(ResUsers, self).create(vals_list)
        
        # For each new portal user, check if there's an employee with the same email
        for user in users:
            if user.has_group('base.group_portal') and not user.employee_id and user.email:
                employee = self.env['hr.employee'].sudo().search([
                    ('work_email', '=', user.email),
                    '|', ('portal_user_id', '=', False), ('portal_user_id', '=', user.id)
                ], limit=1)
                
                if employee:
                    employee.sudo().write({'portal_user_id': user.id})
        
        return users
    
    def write(self, vals):
        """Override write to handle employee synchronization."""
        res = super(ResUsers, self).write(vals)
        
        # If email is changed, update the link with employees
        if 'email' in vals and vals.get('email'):
            for user in self.filtered(lambda u: u.has_group('base.group_portal')):
                if not user.employee_id:
                    employee = self.env['hr.employee'].sudo().search([
                        ('work_email', '=', user.email),
                        '|', ('portal_user_id', '=', False), ('portal_user_id', '=', user.id)
                    ], limit=1)
                    
                    if employee:
                        employee.sudo().write({'portal_user_id': user.id})
        
        return res
