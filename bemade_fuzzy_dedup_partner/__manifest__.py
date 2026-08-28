{
    "name": "Fuzzy Deduplication - Contacts",
    "version": "19.0.1.0.2",
    "category": "Productivity/Data Cleaning",
    "summary": "Suffix- and punctuation-insensitive matching key for contact deduplication",
    "description": """
Fuzzy Deduplication - Contacts
==============================

``bemade_fuzzy_dedup`` compares whatever field a target names, and ``pg_trgm``
already folds case and treats punctuation as a separator. What it does not do
is know that ``Northwind`` and ``Northwind Inc.`` are the same company: on
short names the trailing legal form costs enough trigrams to push the pair
under the threshold.

This module adds a stored ``dedup_key`` to ``res.partner`` holding the name
folded to a comparable form -- accents removed, lowercased, punctuation and
whitespace stripped, and common legal suffixes (``inc``, ``ltd``, ``llc``,
``corp``, ``ltee``, ...) removed -- and ships a deduplication target pointing
at it.

Scope
-----

Every contact takes part, children included. Duplicate contacts under one
company are deduplicated against each other, which is a real need: the same
person entered twice under one household or organisation.

Contacts under *different* parents are never compared, however identical their
names, and that restriction is load-bearing rather than a nicety. Child
contacts are routinely named after a role rather than a person -- "Accounts
Payable", "Reception", "Comptes payables" -- so they fold to an identical key
while being entirely different people at entirely different companies. On a
real database of ~36k partners, ~81% of which were child contacts, comparing
across parents produced single groups of 811, 729 and 596 records consisting
purely of role names.

The engine enforces that restriction in SQL for any model carrying a
``parent_id``, so it holds however this target is later re-scoped.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["bemade_fuzzy_dedup"],
    "data": [
        "data/bemade_dedup_target_data.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
