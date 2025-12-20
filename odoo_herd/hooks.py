from openupgradelib import openupgrade


def post_remove_old_module(env):
    if openupgrade.is_module_installed(env.cr, "odoo_herd"):
        env["ir.module.module"].search(
            [("name", "=", "odoo_herd")]
        ).button_uninstall()
        env.cr.commit()
