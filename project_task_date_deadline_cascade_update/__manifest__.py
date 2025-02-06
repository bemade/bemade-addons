{
    'name': 'Project Task Date Deadline Cascade Update',
    'version': '17.0.0.1',
    'category': 'Project',
    'summary': 'Automatically update child task deadlines when parent task deadline changes.',
    'description': """
        This module ensures that when a parent task's deadline is updated, all child tasks' deadlines are automatically updated to match.
    """,
    'author': 'Bemade',
    'license': 'LGPL-3',
    'website': 'https://www.bemade.org',
    'depends': [
        'project',
        'project_enterprise'
    ],
    'data': [
    ],
    'installable': True,
    'auto_install': False,
}
