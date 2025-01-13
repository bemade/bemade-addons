{
    'name': 'Task Nuker',
    'version': '17.0.1.0.0',
    'category': 'Project',
    'summary': 'Add ability to nuke intermediate tasks while preserving hierarchy',
    'description': """
This module adds a 'Nuke' button on tasks that have both parent and child tasks.
When activated:
- Requests confirmation
- Reassigns all child tasks to the parent task
- Deletes the intermediate task
- Logs the action in the chatter of both parent and child tasks
    """,
    'author': 'DurPro',
    'website': 'https://www.durpro.com',
    'depends': [
        'project',
    ],
    'data': [
        'views/project_task_views.xml',
    ],
    'assets': {},
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}