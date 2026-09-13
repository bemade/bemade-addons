#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    License: LGPL-3
#
{
    "name": "BOM generation from variant attribute rules",
    "version": "19.0.1.3.0",
    "summary": "Generate a variant's bill of materials on demand from attribute-driven rules",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Manufacturing/Manufacturing",
    "license": "LGPL-3",
    "depends": [
        "mrp",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/mrp_bom_rule_set_views.xml",
        "views/mrp_bom_slot_views.xml",
        "views/mrp_bom_rule_views.xml",
        "views/product_attribute_views.xml",
        "views/mrp_bom_views.xml",
        "views/product_views.xml",
        "views/mrp_menus.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mrp_bom_variant_rule/static/src/scss/mrp_bom_rule_set_form.scss",
        ],
    },
    "demo": [],
    "installable": True,
    "auto_install": False,
}
