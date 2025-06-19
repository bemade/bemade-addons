# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    portal_user_id = fields.Many2one(
        'res.users', 
        string='Portal User',
        groups="hr.group_hr_user",
        help="Portal user linked to this employee"
    )
    
    has_portal_access = fields.Boolean(
        string='Has Portal Access',
        compute='_compute_has_portal_access',
        store=True,
        help="Indicates if this employee has portal access"
    )
    
    @api.depends('user_id', 'portal_user_id')
    def _compute_has_portal_access(self):
        """Determine if the employee has portal access through a portal user."""
        for employee in self:
            employee.has_portal_access = bool(employee.portal_user_id) or (
                employee.user_id and employee.user_id.has_group('base.group_portal')
            )
    
    def action_grant_portal_access(self):
        """Create a portal user for the employee."""
        self.ensure_one()
        
        # Check if employee already has a portal user
        if self.portal_user_id:
            raise UserError(_("This employee already has portal access."))
        
        # Check if employee has an email
        if not self.work_email:
            raise UserError(_("You must set a work email address for this employee to create a portal user."))
        
        # Check if the email is already used by another user
        existing_user = self.env['res.users'].sudo().search([('login', '=', self.work_email)], limit=1)
        if existing_user:
            if existing_user.has_group('base.group_portal'):
                # Link the existing portal user to this employee
                self.portal_user_id = existing_user.id
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Portal Access'),
                        'message': _('This employee is now linked to the existing portal user with the same email.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("The email address is already used by another user who is not a portal user."))
        
        # Create a new portal user
        values = {
            'name': self.name,
            'login': self.work_email,
            'email': self.work_email,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            'employee_id': self.id,
        }
        
        # Add company if set on employee
        if self.company_id:
            values['company_ids'] = [(6, 0, [self.company_id.id])]
            values['company_id'] = self.company_id.id
        
        # Create the user and generate a random password
        user = self.env['res.users'].sudo().create(values)
        user.partner_id.write({
            'phone': self.work_phone,
            'mobile': self.mobile_phone,
        })
        
        # Send reset password email
        user.action_reset_password()
        
        # Link the portal user to the employee
        self.portal_user_id = user.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access'),
                'message': _('Portal access has been granted to %s. An invitation email has been sent.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_revoke_portal_access(self):
        """Revoke portal access for the employee."""
        self.ensure_one()
        
        if not self.portal_user_id:
            raise UserError(_("This employee doesn't have portal access."))
        
        portal_user = self.portal_user_id
        
        # Unlink the portal user from the employee
        self.portal_user_id = False
        
        # Archive the portal user
        portal_user.sudo().active = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access'),
                'message': _('Portal access has been revoked from %s.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
