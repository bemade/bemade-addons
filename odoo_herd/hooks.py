from openupgradelib import openupgrade


def post_remove_old_module(env):
    if openupgrade.is_module_installed(env.cr, "k8s_odoo_manager"):
        env["ir.module.module"].search(
            [("name", "=", "k8s_odoo_manager")]
        ).button_uninstall()
        env.cr.commit()
