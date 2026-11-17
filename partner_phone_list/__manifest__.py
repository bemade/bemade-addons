# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Contact Phone Numbers List",
    "version": "19.0.1.1.0",
    "category": "Contacts",
    "summary": "A typed, ordered list of phone numbers per contact; "
    "Phone = the top number, Mobile = the first mobile number.",
    "description": """
Contact Phone Numbers List
==========================

Odoo 19.0 keeps a single ``phone`` field on contacts (``mobile`` was removed in
18.2). Real contacts have several numbers: a mobile, an office line with an
extension, a toll-free number, a fax. This module gives every contact a short,
**typed and ordered list of phone numbers**.

On the contact form, in the child-contact popup and in the simplified contact
form (the contact pop-up of the mail composer, followers, calendar attendees
and "send" wizards), Phone and Mobile show as plain text (click to call). A small phonebook icon next to them opens a
dialog with the editable list of numbers. The dialog edits the contact being
shown, so it works on a new contact and inside the child-contact popup too:
"Save" saves an existing contact; on a new contact or a child contact "Done"
keeps the changes for the contact's own Save.

Each number has:

- a **type**: Mobile, Office, Direct line, Toll-free, Home, Fax or Other;
- the **number**. Forms format it on input in the international format
  (phone_validation, with the contact's country or the company's:
  ``5145550101`` becomes ``+1 514-555-0101``). Numbers written by other apps,
  imports or scripts are stored as written, like the standard Phone field,
  unless the setting **Store phone numbers in international format**
  (Settings > General Settings > Contacts, off by default) is on: then every
  written number is stored formatted, whoever writes it. A value that does
  not parse, or that would lose digits, is kept as typed. A sanitized E.164
  copy is used for matching and search;
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
  writing ``phone``. Whoever may change a contact's Phone or Mobile (a portal
  user included) changes its list: no access rights on the number model are
  needed for that; editing the list itself (the phonebook dialog) needs them.
- When a form saves the list and Phone together, the list wins.
- Searching contacts by phone finds a contact by **any** of its numbers.
- Merging contacts keeps every number of every merged contact (duplicates
  removed) and recomputes Phone and Mobile on the kept contact. Duplicating a
  contact copies its list.
- Changing the list is logged in the chatter (Phone keeps its tracking).
- Text messages: the SMS button shows next to Mobile numbers only (Mobile,
  Phone when the top number is a mobile, Mobile lines of the list), and only
  when the SMS module is installed and the company can send SMS (an SMS
  provider such as Twilio, or an Odoo IAP SMS account).
- A record that pushes its phone to the contact and keeps a copy (a company,
  or other modules' tickets, tasks...) can call
  ``res.partner._phone_list_resync`` after its write so its copy shows the
  stored, formatted number (done here for companies).
- The contacts list gives the Phone (and Mobile) column a minimum width.

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
    "depends": ["base", "base_setup", "mail", "phone_validation"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "partner_phone_list/static/src/**/*",
        ],
        "web.assets_tests": [
            "partner_phone_list/static/tests/tours/partner_phone_list_tour.js",
        ],
    },
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
