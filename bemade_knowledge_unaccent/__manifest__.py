{
    "name": "Knowledge: Accent-Insensitive Search",
    "version": "19.0.1.0.0",
    "summary": "The Knowledge search box ignores accents again, in article "
    "titles and article text.",
    "description": """
Knowledge: Accent-Insensitive Search
====================================

With the PostgreSQL ``unaccent`` extension installed, Odoo ignores accents in
every search: looking for *securite* finds *Sécurité*. The search box of the
Knowledge app does not follow that rule. It searches article titles and
article text with its own database query, so *securite* finds neither an
article titled *Sécurité incendie* nor one whose text says
*procédure de sécurité*.

This module makes that search box accent-insensitive again:

* **Article text** - the full-text search configuration used by Knowledge
  (``knowledge_config``) passes every word through the ``unaccent``
  dictionary before indexing it, and the full-text index on the article text
  is rebuilt. Accented and unaccented queries both match, and the matching
  words are highlighted in the text preview as before.
* **Article titles** - after the standard search, the articles whose title
  matches the query once accents are ignored are added to the results (and
  listed ahead of the articles that only match in their text), with the usual
  access rules. The number of results never exceeds the requested limit.

Nothing else changes: other searches already ignore accents.

Requirements
------------

The ``unaccent`` PostgreSQL extension must be installed in the database
(see Odoo's ``--unaccent`` option). Without it the module only logs a message
on installation and changes nothing.

Installation and uninstallation
-------------------------------

Installing or upgrading the module rebuilds the full-text index of the article
text once (a few seconds for some hundreds of articles). Uninstalling it
restores the standard configuration and rebuilds the index again.
""",
    "category": "Productivity/Knowledge",
    "author": "Bemade Inc.",
    "maintainer": "Denis Durepos <denis@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["knowledge"],
    "data": [],
    "uninstall_hook": "_uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
