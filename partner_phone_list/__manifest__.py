# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Contact Phone Numbers List",
    "version": "19.0.1.0.0",
    "category": "Contacts",
    "summary": "A typed, ordered list of phone numbers per contact; "
    "Phone = the top number, Mobile = the first mobile number.",
    "description": """
Contact Phone Numbers List
==========================

Odoo 19.0 keeps a single ``phone`` field on contacts (``mobile`` was removed in
18.2). Real contacts have several numbers: a mobile, an office line with an
extension, a toll-free number, a fax. This module gives every contact a short,
**typed and ordered list of phone numbers**, shown in place of the Phone field
on the contact form and in the child-contact popup.

Each number has:

- a **type**: Mobile, Office, Direct line, Toll-free, Home, Fax or Other;
- the **number** as entered (formatted to the international form when typed in
  the form, like the standard Phone field), plus a sanitized E.164 copy used for
  matching and search;
- an optional **extension** and **label** (e.g. "after hours");
- a **position**: drag the rows to reorder them; the top row is the primary
  number.

Compatibility contract
----------------------

Everything that reads or writes ``phone`` keeps working:

- ``phone`` is the **top number** of the list (with " ext. " and its extension
  when it has one). It stays a stored field, so lists, kanban cards, reports,
  searches and exports are unchanged.
- ``mobile`` comes back as a stored field holding the **first Mobile-type
  number**. SMS and other phone features pick it first, through the standard
  ``mobile`` / ``phone`` lookup.
- **Every write to** ``phone`` **or** ``mobile`` **lands in the list**: writing
  a number already in the list (in any format) moves it to the top (Phone) or
  types it Mobile (Mobile), without creating a duplicate; a new number is added
  (on top for Phone, right after the top for Mobile); clearing Phone removes the
  top number, clearing Mobile removes the first mobile number. Other numbers are
  never deleted. This covers leads, tickets, tasks, employees, users,
  companies, portal and website address forms, imports and any other module
  writing ``phone``.
- When a form saves the list and Phone together, the list wins.
- Searching contacts by phone finds a contact by **any** of its numbers.
- Merging contacts keeps every number of every merged contact (duplicates
  removed) and recomputes Phone and Mobile on the kept contact. Duplicating a
  contact copies its list.
- Changing the list is logged in the chatter (Phone keeps its tracking).

Installation
------------

At install, one number line is created per contact from its current Phone (and
from a ``mobile`` column if the database still has one), with the values
unchanged, so installing changes no displayed phone number. Splitting legacy
values that hold several numbers, or retyping numbers, is left to a
project-specific module.
""",
    "author": "Bemade Inc.",
    "maintainer": "Denis Durepos",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["base", "mail", "phone_validation"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "partner_phone_list/static/tests/tours/partner_phone_list_tour.js",
        ],
    },
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
