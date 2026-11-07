{
    "name": "Partner Merge in Batches",
    "version": "19.0.1.0.0",
    "category": "Hidden/Tools",
    "summary": "Merge more than 3 contacts at once, in batches of 3",
    "description": """
Partner Merge in Batches
========================

Odoo refuses to merge more than 3 contacts at once ("For safety reasons, you
cannot merge more than 3 contacts together"). This limit applies to the
Contacts *Merge* action and to every *Data Cleaning* duplicate group, which
then cannot be merged in one click when it holds 4 contacts or more.

This module lifts the limit by running a merge of N contacts as successive
standard merges of at most 3 contacts (the kept contact plus 2 others), all
into the same kept contact:

* The kept (destination) contact is chosen exactly as Odoo does: the one picked
  in the wizard or by Data Cleaning, otherwise Odoo's default ordering.
* Odoo's safety checks are first run on the **whole** set (a contact and one of
  its parents, contacts linked to more than one user, different emails for a
  non-administrator), so splitting into batches can never dodge them. They then
  keep running on every batch, as do the checks added by other modules.
* The merge is all-or-nothing: every batch runs in the same transaction, so an
  error in any batch cancels the whole merge.

Merges of 3 contacts or fewer are left entirely to Odoo.
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [],
    "installable": True,
    "auto_install": False,
}
