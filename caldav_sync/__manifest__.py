#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "CalDAV Synchronization",
    "version": "18.0.0.8.0",
    "license": "LGPL-3",
    "category": "Productivity",
    "summary": "Synchronize Odoo Calendar Events with CalDAV Servers",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base", "calendar"],
    "external_dependencies": {
        "python": ["caldav", "icalendar", "markdownify", "markdown2"],
    },
    "images": ["static/description/images/main_screenshot.png"],
    "data": [
        "views/res_users_views.xml",
        "data/caldav_sync_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
