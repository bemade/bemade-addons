{
    "name": "Project Task Templates",
    "version": "17.0.1.0.0",
    "category": "Project",
    "summary": "Create and manage reusable task templates for projects",
    "description": """
Project Task Templates
======================

This module provides a framework for creating and managing reusable task templates
that can be used to quickly generate project tasks with predefined configurations.

Key Features
------------

* Define reusable task templates with common fields (name, description, planned hours)
* Support for task hierarchies (templates can define parent tasks and subtasks)
* Templates can specify default assignees, tags, and other task properties
* Track template changes through the chatter
* Copy templates to create variations

Technical Details
-----------------

* Introduces project.task.template model that defines the structure of tasks to create
* Links generated tasks back to their originating templates
* Templates are structural only - they define what tasks to create but don't control runtime behavior
* Changes to templates do not affect tasks that were already created
    """,
    "author": "Bemade Inc",
    "website": "https://www.bemade.org",
    "depends": [
        "project",
        "mail",  # For chatter support
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_task_template_views.xml",
        "views/project_menus.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
