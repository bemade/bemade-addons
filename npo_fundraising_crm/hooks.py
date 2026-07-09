# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


def post_init_hook(env):
    """Re-load this module's translations with ``overwrite=True``.

    The default translation load uses ``overwrite=False``, which *skips* any
    term that already has a value in the target language. Since ``crm`` has
    already translated "Opportunity" -> "Opportunité", "Salesperson" ->
    "Vendeur", etc. into ``fr_CA``, our ``fr_CA.po`` overrides would silently
    do nothing. Forcing an overwrite here makes the fundraising vocabulary win
    deterministically on install/upgrade (mirror ``--i18n-overwrite`` for CI
    redeploys).
    """
    module = env["ir.module.module"].search(
        [("name", "=", "npo_fundraising_crm")], limit=1
    )
    if module:
        module._update_translations(overwrite=True)
