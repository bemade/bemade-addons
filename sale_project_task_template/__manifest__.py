{
    "name": "Sales Project Task Templates",
    "version": "17.0.1.0.0",
    "summary": "Link products to task templates for automatic task creation from sales",
    "description": """
This module extends project task templates to work with sales orders:

Features:
* Link task templates to service products
* Automatically create tasks from templates when confirming sales orders
* Support for customer-specific task templates
* Inherit customer from template or sale order
* Maintain proper task-sale relationships for billing

Technical Details:
* Extends project.task.template to add customer support
* Integrates with sale_project for proper task creation and linking
* Inherits partner handling logic from sale_project
""",
    "author": "Durpro",
    "website": "https://durpro.com",
    "category": "Services/Project",
    "depends": [
        "project_task_template",
        "sale_project",
    ],
    "data": [
        "views/product_views.xml",
        "views/project_task_template_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "auto_install": True,  # Auto-install if project_task_template and sale_project are installed
}
