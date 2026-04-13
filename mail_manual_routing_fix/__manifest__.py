# -*- coding: utf-8 -*-
{
    "name": "Lost Messages Routing - Bug Fixes",
    "version": "18.0.1.0.0",
    "category": "Discuss",
    "summary": "Fixes HTML escaping and threading preservation bugs in mail_manual_routing",
    "description": """
This module fixes critical bugs in the mail_manual_routing module:

1. **HTML Escaping Fix**: The original module escapes all message bodies,
   breaking HTML emails. This fix respects the body_is_html flag.

2. **Threading Preservation**: When attaching lost messages to records,
   the original module loses parent_id, in_reply_to, and references.
   This fix preserves threading metadata.

3. **Lost Origin Tracking**: Messages routed from Lost Messages are marked
   with lost_origin flag, lost_routed_date and lost_routed_by for traceability.
    """,
    "author": "Bemade Inc.",
    "website": "https://bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail_manual_routing",
    ],
    "data": [
        "views/mail_message_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
