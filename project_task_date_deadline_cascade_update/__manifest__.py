{
    'name': 'Project Task Date Deadline Cascade Update',
    'version': '17.0.0.1',
    'category': 'Project',
    'summary': 'Automatically update child task deadlines when parent task deadline changes.',
    'description': """
        This module ensures that when a parent task's deadline is updated, all child tasks' deadlines are automatically updated to match.
    """,
    'author': 'Your Name',
    'license': 'AGPL-3',
    'website': 'https://www.yourwebsite.com',
    'depends': ['project'],
    'data': [
        'views/update_deadline_wizard_view.xml',
        'wizard/update_deadline_wizard.xml',
    ],
    'installable': True,
    'auto_install': False,
}
