# -*- coding: utf-8 -*-
{
    'name': 'Employee Portal Access',
    'version': '18.0.1.0',
    'category': 'Human Resources',
    'summary': 'Link portal users to employees',
    'description': """
Employee Portal Access
======================
This module allows to give portal access to employees, similar to how it's done for contacts.
It adds a button on the employee form to create a portal user and ensures proper synchronization
between the employee and the portal user.
    """,
    'depends': ['hr', 'portal', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
