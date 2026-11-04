#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact: marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
#    For full license details, see https://www.gnu.org/licenses/lgpl-3.0.en.html.
#
{
    "name": "Conversation Thread View",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Optional email-thread layout for a conversation, next to the "
    "regular form.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "conversation_base",
        "conversation_draft",
        "conversation_forward",
    ],
    "data": [
        "views/mail_conversation_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "conversation_thread_view/static/src/**/*",
        ],
        "web.assets_tests": [
            "conversation_thread_view/static/tests/tours/thread_view.steps.js",
            "conversation_thread_view/static/tests/tours/thread_view.tour.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
