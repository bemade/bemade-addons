{
    "name": "Odoo Herd Portal",
    "version": "19.0.1.0.0",
    "category": "Administration/Kubernetes",
    "summary": "Client self-service portal for Bemade-hosted Odoo instances",
    "description": """
Odoo Herd Portal
================

Client self-service portal for Bemade-hosted Odoo instances. Extends
``odoo_herd`` to give hosting customers scoped, read-mostly access to the
instances they own, surfaced through the Odoo customer portal (``/my``).

Each ``k8s.odoo.instance`` gains an ``allowed_partner_ids`` link; a portal
user sees an instance only when their commercial partner is among the
allowed partners.

Version 1 features
------------------
* **Access & ownership** -- per-instance ``allowed_partner_ids`` with portal
  record rules scoped to the user's commercial partner.
* **Instance overview** -- instances grouped into Production and Staging
  (from the existing ``environment`` field), showing status, version and URL.
* **Live log viewer** -- live tail of an instance's web and cron pods with
  in-browser search and filtering, streamed by a separate sidecar service and
  authorised by a short-lived signed token. Recent logs only.
* **Backups** -- list and download backups; trigger a backup; restore is
  self-service on staging and back-office only on production.
* **Self-service lifecycle** -- module upgrade and staging refresh, with an
  auto-backup-before-upgrade guardrail and an action audit trail.

Planned (v2)
------------
* Client-initiated staging *creation* within a quota.
* Historical log search backed by Loki.
* Instance restart, implemented as an operator-reconciled action on the
  ``OdooInstance`` CRD.

See ``docs/SPEC.md`` for the full epic specification.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "odoo_herd",
        "portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/k8s_portal_security.xml",
        "views/k8s_cluster_views.xml",
        "views/k8s_odoo_instance_views.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "odoo_herd_portal/static/src/js/log_viewer.js",
        ],
    },
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
