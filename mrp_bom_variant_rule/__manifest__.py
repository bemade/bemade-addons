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
    "version": "18.0.1.0.0",
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
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
