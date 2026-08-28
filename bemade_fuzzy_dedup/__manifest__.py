{
    "name": "Fuzzy Deduplication",
    "version": "19.0.1.0.2",
    "category": "Productivity/Data Cleaning",
    "summary": "Find near-duplicate records on any model using trigram similarity",
    "description": """
Fuzzy Deduplication
===================

Odoo Community detects duplicates only where a field is byte-identical: the
contact deduplication wizard in ``base`` groups partners with a SQL ``GROUP
BY``, and it exists for ``res.partner`` alone. Records differing by a legal
suffix, punctuation or a typo are never proposed, and no other model is
covered at all.

This module adds trigram-similarity matching over the PostgreSQL ``pg_trgm``
extension, for any model.

Enabling a model
----------------

A deduplication target names a model, one stored ``char`` or ``text`` field to
compare, and an optional domain restricting which records take part. Creating
the target builds a GIN trigram index on the column; deleting it drops the
index. There is no further configuration: the similarity threshold is a single
system parameter, and matching is always proposal-only.

Translated fields are supported. Those are stored as JSONB in Odoo 19, so both
the index and the comparison are built on the ``en_US`` value.

Review and merge
----------------

Matching pairs are clustered and materialised as persistent duplicate groups
for review. Nothing is ever merged automatically: a similarity score is not an
identity proof, so disposal stays with the reviewer. Groups are persistent
rather than transient, so a group the reviewer discards is not proposed again
on the next run.

Merging reassigns foreign keys, reference fields and empty values onto the
elected master using the generic helpers Odoo provides in ``base``, then
archives the sources where the model supports it and deletes them where it
does not.

Notes
-----

* ``pg_trgm`` is created by the module if absent. Odoo creates it in
  ``_initialize_db``, but a database built by ``createdb`` plus a restore never
  runs that path, so it cannot be assumed. Where the extension cannot be
  created, targets remain configurable but the pass is skipped.
* Normalising the compared value is left to the model. ``pg_trgm`` already
  folds case and treats punctuation as a separator, so raw names work well;
  where more is wanted -- stripping legal suffixes from company names, say --
  a model supplies a stored normalised field and the target points at that.
* Phonetic matching (``fuzzystrmatch``) is deliberately not used. Those
  functions truncate to roughly four characters, which on multi-word names
  produces unusable false positive rates.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/bemade_dedup_target_views.xml",
        "views/bemade_dedup_group_views.xml",
        "views/menu_views.xml",
        "data/ir_cron_data.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "bemade_fuzzy_dedup/static/tests/tours/fuzzy_dedup_review_tour.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
