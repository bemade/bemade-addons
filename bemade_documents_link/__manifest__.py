{
    "name": "Documents - Link Existing",
    "version": "18.0.1.0.0",
    "summary": "Easily link an existing Documents record (incl. spreadsheets) "
               "to any mail.thread record, from either side.",
    "description": """
Documents - Link Existing
=========================

Adds two generic, reusable entry points for linking an **existing** document
(including a spreadsheet) to a business record, without uploading a new file:

* **From the record side** — a *Link existing document* item appears in the
  cog menu of every ``mail.thread`` form view. It opens a small wizard that
  lets the user pick one or more already-existing, unlinked Documents records
  and links them to the current record.
* **From the Documents side** — a generic *Link to record* server action lets
  the user first choose the target model (limited to ``mail.thread`` models)
  and then the record, reusing the stock Documents ``link_to_record_wizard``.

Linking simply sets ``res_model`` / ``res_id`` on the chosen
``documents.document`` records; no new persistent storage is introduced.
""",
    "category": "Productivity/Documents",
    "author": "Bemade Inc.",
    "maintainer": "Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["documents"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/documents_link_wizard_views.xml",
        "data/ir_actions_server_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_documents_link/static/src/link_document_cog_menu/*.js",
            "bemade_documents_link/static/src/link_document_cog_menu/*.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
}
