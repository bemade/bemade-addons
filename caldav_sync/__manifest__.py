#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "CalDAV Synchronization",
    "version": "19.0.0.8.1",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Productivity",
    "summary": "Synchronize Odoo Calendar Events with CalDAV Servers",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base", "calendar"],
    "external_dependencies": {
        "python": [
            # NOTE: caldav<=2.0.1 calls icalendar.cal.component_factory[objtype]
            # which broke in icalendar 6.0. Bumping to caldav 3.x fixes that
            # but pulls transitive deps that force urllib3>=2.0, which in turn
            # breaks Odoo 19's ir_mail_server (it imports PyOpenSSLContext from
            # urllib3.contrib.pyopenssl, removed in 2.0). Until Odoo upstream
            # catches up, stay on the older mesh: caldav 2.x + icalendar 5.x.
            # See caldav_sync/tests/test_integration.py: it is opt-in only
            # (@tagged('-standard', 'caldav_integration')) because the kwargs
            # path is what those tests exercise.
            "caldav>=1.3.9,<=2.0.1",
            "icalendar<6.0",
            "markdownify",
            "markdown2",
        ],
    },
    "images": ["static/description/images/main_screenshot.png"],
    "data": [
        "views/res_users_views.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
