from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Reload this module's French over the round-1 terms.

    19.0.1.1.0 rewords the visit form note and the « Overbooked » help to
    mention the return delay. On upgrade Odoo maps the old view term onto the
    reworded one and keeps its old French, and it never overwrites a field
    help that already has a translation, so both would stay as in 19.0.1.0.0.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = [
        code for code, _name in env["res.lang"].get_installed() if code.startswith("fr")
    ]
    if langs:
        env["ir.module.module"]._load_module_terms(
            ["bemade_fsm_prep"], langs, overwrite=True
        )
