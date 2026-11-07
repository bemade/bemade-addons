{
    "name": "Partner Parent by Email Domain",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Attach new contacts to their company from the email domain; "
    "ambiguous cases go to an internal triage list",
    "description": """
Partner Parent by Email Domain
==============================

Companies carry an **Email Domain** (e.g. ``example.com``). When an individual
contact without a company is created, or its email changes, the module looks for
companies whose email domain matches the contact's email domain:

* the match is anchored on a label boundary: ``example.com`` matches
  ``@example.com`` and ``@lab.example.com``, never ``@myexample.com``;
* only individual contacts of type *Contact* without a parent are considered,
  company records are never touched;
* candidate companies are the active companies of the current company or shared
  (no company);
* when several configured domains match, the most specific one wins
  (``lab.example.com`` before ``example.com``).

One matching company
    The contact is attached to it, a note is posted in its chatter, and a
    **Detach** button on the contact undoes the guess in one click. With the
    *Suggest only* setting, the contact is queued in the triage list instead.

Several matching companies
    Nothing is written on the contact. It is queued in **Contacts > Unassigned
    contacts**, where the candidate companies are shown as clickable choices on
    each row. Nothing is chosen by default; **Apply assignments** attaches the
    contacts that received a choice. A row closes by itself as soon as the
    contact gets a company by any means.

The module never sends any email. A weekly scheduled action reminds the user
set in the settings when contacts are waiting in the triage list.

Email domains are validated on save: lowercase, no ``@``, no scheme or path, at
least one dot, and not a public mailbox provider (gmail.com, outlook.com, ...).
""",
    "depends": ["contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_partner_views.xml",
        "views/partner_parent_suggestion_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_partner_email_domain/static/src/**/*",
        ],
    },
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "installable": True,
    "auto_install": False,
}
