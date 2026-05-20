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
            # caldav<=2.0.1 calls icalendar.cal.component_factory[objtype]
            # in vcal.create_ical; that subscriptable API was removed in
            # icalendar 6.0, so save_event(**kwargs) crashes against any
            # icalendar 6+. caldav 3.x dropped that pattern and matches the
            # icalendar 6+/recurring_ical_events 3+ ecosystem.
            "caldav>=3.0,<4.0",
            "icalendar>=6.0",
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
