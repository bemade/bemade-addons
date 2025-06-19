# -*- coding: utf-8 -*-
{
    'name': 'Portal Planning',
    'version': '18.0.1.0',
    'category': 'Human Resources/Planning',
    'summary': 'Allow portal users to access their planning',
    'description': """
Portal Planning
===============
This module extends the Planning module to allow employees with portal access to view and manage their planning.
    """,
    'depends': [
        'employee_portal', 
        'planning', 
        'mail', 
        'analytic', 
        'hr_timesheet', 
        'hr_skills'
    ],
    'data': [
        'security/portal_planning_security.xml',
        'security/ir.model.access.csv',
        'data/portal_planning_data.xml',
        'data/ir_sequence_data.xml',
        'views/portal_planning_templates.xml',
        'views/portal_planning_slot_templates.xml',
        'views/portal_planning_slot_create_template.xml',
        'views/portal_planning_exchange_templates.xml',
        'views/portal_planning_views.xml',
        'views/planning_slot_views.xml',
        'views/portal_planning_modification_views.xml',
        'views/portal_planning_exchange_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'portal_planning/static/src/css/portal_planning.css',
            'portal_planning/static/src/scss/portal_planning.scss',
            'portal_planning/static/src/js/portal_planning.js',
            'portal_planning/static/src/js/portal_planning_calendar.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OEEL-1',
}
