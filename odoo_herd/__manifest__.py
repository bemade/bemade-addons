{
    "name": "Odoo Herd",
    "version": "19.0.1.1.0",
    "category": "Administration/Kubernetes",
    "summary": "Manage your herd of Odoo instances across Kubernetes clusters",
    "description": """
Odoo Herd
=========
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
        "views/k8s_upgrade_views.xml",
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
            "openupgradelib",
        ],
    },
    "assets": {
        "web.assets_backend": [
            "odoo_herd/static/src/css/k8s_manager.css",
            "odoo_herd/static/src/js/k8s_dashboard_component.js",
            "odoo_herd/static/src/js/s3_upload_widget.js",
            "odoo_herd/static/src/js/instance_list_view.js",
            "odoo_herd/static/src/xml/k8s_dashboard_component.xml",
            "odoo_herd/static/src/xml/s3_upload_widget.xml",
            "odoo_herd/static/src/xml/instance_list_view.xml",
        ],
    },
    "post_init_hook": "post_remove_old_module",
}
