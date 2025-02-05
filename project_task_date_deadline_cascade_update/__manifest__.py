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
    'depends': [
        'project',
        'project_enterprise'
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'data/res_config_settings_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
