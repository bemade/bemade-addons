{
    "name": "Data Cleaning - Fuzzy Deduplication",
    "version": "19.0.1.0.0",
    "category": "Productivity/Data Cleaning",
    "summary": "Find near-duplicate contacts that exact-match deduplication misses",
    "description": """
Data Cleaning - Fuzzy Deduplication
===================================

Odoo's deduplication (``data_merge``) generates duplicate candidates with a SQL
``GROUP BY`` on the rule's field. Two records are only ever proposed as
duplicates when that field is byte-identical -- or, when the ``unaccent``
extension is available, identical after ``lower(unaccent(...))``. The similarity
percentage shown on a group is computed *after* the group exists and only
filters it; it never widens the candidate set.

Consequently the common migration duplicate is invisible to the standard tool:

* ``Northwind`` vs ``Northwind Inc.`` -- differing legal suffix
* ``A & B Filtration`` vs ``A&B Filtration`` -- differing punctuation
* ``Global Milling and Consulting`` vs ``Global Milling & Consulting LLC``
* ``Orbit Technologies`` vs ``Orbit technologies`` -- differing case

This module adds two candidate-generation strategies on top of the standard
one, both of which surface their results in the standard Data Cleaning review
queue. Nothing is merged automatically and no core method is overridden.

Normalized key matching
-----------------------

A stored ``dedup_key`` field is added to ``res.partner``, holding the partner
name folded to a comparable form: accents removed, lowercased, punctuation and
whitespace stripped, and common legal suffixes (``inc``, ``ltd``, ``llc``,
``corp``, ``ltee``, ...) removed. A deduplication rule on this field lets the
standard engine group records whose names differ only in those respects, using
its existing ``GROUP BY`` machinery.

Trigram similarity matching
---------------------------

Normalized keys still require the remaining characters to match exactly. A
second pass uses the PostgreSQL ``pg_trgm`` extension to compare every pair of
``dedup_key`` values and proposes those scoring above a configurable
similarity threshold. Matching pairs are materialised as standard
``data_merge.group`` records, so they are reviewed and merged through the
normal Data Cleaning interface.

``dedup_key`` carries a GIN trigram index, which turns this pass from a
quadratic scan into an index lookup.

Notes
-----

* ``pg_trgm`` is created automatically by Odoo when a database is initialised,
  so no additional PostgreSQL extension is required.
* Phonetic matching (``fuzzystrmatch``: ``soundex``, ``dmetaphone``) is
  deliberately **not** used. Those functions truncate to roughly four
  characters, which on multi-word company names produces unusable false
  positive rates.
* This module changes which duplicates are *proposed*. It does not change how
  duplicates are merged, and it does not enable automatic merging.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["data_cleaning"],
    "data": [
        "data/data_merge_data.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
