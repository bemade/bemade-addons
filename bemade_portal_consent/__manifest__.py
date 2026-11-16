# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Consent',
    'version': '19.0.1.0.1',
    'category': 'Website/Portal',
    'summary': 'Versioned consent documents portal users accept before using the portal, with an acceptance log.',
    'description': """
Bemade Portal Consent
=====================

Versioned consent documents (privacy policy, confidentiality undertaking,
terms of use…) that portal users must accept before they use the portal,
with a log of every acceptance. Written for Quebec's Law 25 (Act respecting
the protection of personal information in the private sector): the consent
is explicit, tied to the exact text the person saw, and kept.

Community only; depends on ``portal`` only. Works with or without
``bemade_portal_kit`` (the gate also covers the kit's ``/my/app`` pages).

Documents and versions
----------------------
*Settings › Users & Companies › Consents* (administrators, and the
« Consent Manager » group, which a consumer can imply from one of its own
groups).

* A **document** (``portal.consent.document``) has a unique ``code``, a
  translatable name and its **versions**.
* A **version** (``portal.consent.version``) holds the text (translatable
  HTML). It is written as a draft, then **published** through the
  « Publish » wizard. A published version is read-only: its text can no
  longer change, it cannot be deleted. Translate the text before publishing.
* The wizard's « Require a new acceptance » box decides whether users who
  accepted an earlier version must accept again. The first published
  version of a document always requires it.
* The **required version** of a document is its latest published version
  that requires a new acceptance. A user is **compliant** with a document
  when they accepted its required version or a later published one.
* An **acceptance** (``portal.consent.acceptance``) records the version,
  the user, the partner, the time, the IP address and the browser's user
  agent. It is never edited; only an administrator can delete one
  (retention is the consumer's concern). A portal user only reads their
  own acceptances.
* A document's « Pending users » button lists the portal users who must
  accept it and have not (computed on demand from the hook below).

The gate
--------
An authenticated portal user (never an internal user nor the public user)
who requests an ``auth='user'`` HTTP page under one of the gated prefixes
while a document is pending is redirected (303) to ``/my/consent``, the
original page kept in ``?redirect=``. The consent page shows the pending
documents one after the other (« I accept », « Log out ») and then sends
the user to the original page. The ``redirect`` target is a relative path
only; anything else falls back to ``/my``. URL language prefixes
(``/fr/my/...``) are handled. Public routes (``auth='public'``: web
manifests, service workers, icons) and JSON routes are never gated.

How a consumer uses it
----------------------
1. Depend on ``bemade_portal_consent``.
2. Declare which documents a user must accept by overriding the hook on
   ``res.users`` (it runs as superuser, on one user)::

       class ResUsers(models.Model):
           _inherit = 'res.users'

           def _portal_consent_documents(self):
               documents = super()._portal_consent_documents()
               if self.partner_id.is_member:
                   documents |= self.env.ref('my_addon.consent_members')
               return documents

   ``res.users._portal_consent_pending()`` returns the documents the user
   has not complied with (archived documents and documents without a
   published version are never pending).
3. Seed the document and its first version as a draft in a ``noupdate``
   data file. Nothing is gated until someone publishes a version::

       <odoo noupdate="1">
           <record id="consent_members" model="portal.consent.document">
               <field name="name">Members' privacy policy</field>
               <field name="code">my_addon_members</field>
           </record>
           <record id="consent_members_v1" model="portal.consent.version">
               <field name="document_id" ref="consent_members"/>
               <field name="body">&lt;p&gt;PLACEHOLDER TEXT&lt;/p&gt;</field>
           </record>
       </odoo>

4. Gated prefixes: the system parameter ``bemade_portal_consent.prefixes``
   (comma-separated paths, default ``/my``). Add a prefix to gate more
   pages, e.g. ``/my,/club``.
5. To let a back-office group manage the documents, imply
   ``bemade_portal_consent.group_portal_consent_manager`` from it.
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['portal'],
    'data': [
        'security/portal_consent_security.xml',
        'security/ir.model.access.csv',
        'wizard/portal_consent_publish_wizard_views.xml',
        'views/portal_consent_views.xml',
        'views/portal_consent_templates.xml',
    ],
    'installable': True,
    'application': False,
}
