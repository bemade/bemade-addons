# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class EmployeePortal(CustomerPortal):
    
    def _prepare_portal_layout_values(self):
        """Add employee to portal values."""
        values = super(EmployeePortal, self)._prepare_portal_layout_values()
        
        if request.env.user.has_group('base.group_portal'):
            employee = request.env.user.employee_id
            values['employee'] = employee
        
        return values
    
    def _prepare_home_portal_values(self, counters):
        """Add employee-related counters to portal home."""
        values = super(EmployeePortal, self)._prepare_home_portal_values(counters)
        
        # Only proceed if user is a portal user with an employee
        if not request.env.user.has_group('base.group_portal') or not request.env.user.employee_id:
            return values
        
        return values
