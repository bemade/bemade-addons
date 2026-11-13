# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Attachments: Convert HEIC Photos to JPEG",
    "version": "19.0.1.0.0",
    "category": "Productivity/Discuss",
    "summary": "iPhone .heic photos are stored as JPEG so that Odoo and browsers can show them.",
    "description": """
Convert HEIC Photos to JPEG
===========================

iPhones save photos as HEIC (``.heic`` / ``.heif``), a format that browsers
cannot display: such an attachment shows as a generic file in Odoo, without
preview. This module stores them as JPEG instead.

Features
--------

* **On upload**: any attachment created or rewritten with HEIC content is
  converted to JPEG (quality 90, turned upright, EXIF kept apart from the
  orientation) and renamed ``.jpg``. It covers every flow that creates an
  ``ir.attachment``: chatter, record attachments, expense receipts,
  helpdesk/field service/quality photos, inbound email attachments.
  HEIC is recognised by its mimetype, its ``.heic``/``.heif`` extension or its
  content (browsers often send ``application/octet-stream``).
* **Never blocks an upload**: a file that cannot be converted (corrupt,
  decoder missing) is kept as uploaded and a warning is logged.
* **Convert to JPEG** button on the HEIC attachment cards of the chatter, for
  internal users who can edit the record. On failure it shows a clear
  bilingual (French, then English) message.
* **Backfill**: the scheduled action *Attachments: convert stored HEIC images
  to JPEG* (shipped **inactive**) converts the HEIC attachments stored before
  the module, 50 per batch with a commit after each batch, and deactivates
  itself when none is left. Files it cannot convert are flagged and skipped.

Scope
-----

* Plain attachments only: files stored in a binary field of a record
  (``res_field``) are left alone.
* Works with any attachment storage (database, filestore, ``fs_attachment``
  object storage): the content is rewritten through the ORM, so the old file
  is garbage-collected the usual way.
* Odoo's standard image auto-resize (``base.image_autoresize_max_px``) then
  applies to the JPEG as to any uploaded JPEG.

Requires the Python package ``pillow-heif`` < 1.0 (prebuilt wheels bundle
libheif; 1.x needs a newer Pillow than Odoo 19 pins on Python 3.12).
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "depends": ["mail"],
    # pillow-heif 1.x requires Pillow >= 11.1, newer than what Odoo 19 pins on
    # Python 3.12 (Pillow 10.2): an unpinned install would upgrade Pillow.
    "external_dependencies": {"python": ["pillow_heif<1"]},
    "data": [
        "data/ir_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_attachment_heic/static/src/**/*",
        ],
        "web.assets_tests": [
            "bemade_attachment_heic/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
