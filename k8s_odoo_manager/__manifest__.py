{
    "name": "Kubernetes Odoo Manager",
    "version": "18.0.1.0.0",
    "category": "Administration/Kubernetes",
    "summary": "Manage Odoo instances through Kubernetes operator",
    "description": """
Kubernetes Odoo Manager
=======================
This module allows you to:
* Connect to Kubernetes clusters running the Odoo operator
* Manage OdooInstance custom resources
* Monitor instance status and health
* Perform operations on managed Odoo instances

Features:
* Cluster connection management with secure kubeconfig storage
* Real-time OdooInstance discovery and synchronization
* Status monitoring and alerting
* Centralized management interface for multiple clusters
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "OPL-1",
    "depends": [
        "base",
        "web",
        "mail",
    ],
    "data": [
        # Security
        "security/k8s_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/k8s_data.xml",
        # Wizards (must be loaded before views that reference them)
        "wizards/k8s_cluster_test_wizard_views.xml",
        "wizards/k8s_sync_instances_wizard_views.xml",
        "wizards/k8s_upgrade_wizard_views.xml",
        "wizards/k8s_create_instance_wizard_views.xml",
        "wizards/k8s_delete_instance_wizard_views.xml",
        "wizards/k8s_restore_backup_wizard_views.xml",
        "wizards/k8s_backup_wizard_views.xml",
        "wizards/k8s_upload_backup_wizard_views.xml",
        # Views
        "views/k8s_dashboard_views.xml",
        "views/k8s_cluster_views.xml",
        "views/k8s_odoo_instance_views.xml",
        "views/k8s_odoo_instance_template_views.xml",
        "views/k8s_s3_config_views.xml",
        "views/k8s_backup_views.xml",
        "views/k8s_restore_views.xml",
        "views/k8s_menu_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
    "external_dependencies": {
        "python": [
            "kubernetes",
            "pyyaml",
            "boto3",
        ],
    },
    "assets": {
        "web.assets_backend": [
            "k8s_odoo_manager/static/src/css/k8s_manager.css",
            "k8s_odoo_manager/static/src/js/k8s_dashboard_component.js",
            "k8s_odoo_manager/static/src/js/s3_upload_widget.js",
            "k8s_odoo_manager/static/src/js/instance_list_view.js",
            "k8s_odoo_manager/static/src/xml/k8s_dashboard_component.xml",
            "k8s_odoo_manager/static/src/xml/s3_upload_widget.xml",
            "k8s_odoo_manager/static/src/xml/instance_list_view.xml",
        ],
    },
}
