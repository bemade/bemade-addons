#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "OpenWebUI Base",
    "version": "18.0.0.1.0",
    "license": "LGPL-3",
    "category": "Tools",
    "summary": "Base module for OpenWebUI integration",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base", "base_setup"],
    "external_dependencies": {
        "python": ["openwebui-client>=0.3.0"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/openwebui_provider_views.xml",
        "views/openwebui_model_views.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
