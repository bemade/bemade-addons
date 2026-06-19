# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature B -- client-facing instance overview portal controller.

Extends the standard ``CustomerPortal`` with:

* an "Odoo Instances" card + count on ``/my`` (the portal home);
* ``/my/instances`` -- the user's instances grouped into Production and
  Staging by the ``environment`` field;
* ``/my/instances/<id>`` -- a per-instance detail page.

Isolation is enforced entirely by Feature A's record rule: the controller
issues an ordinary ``search([])`` / ``browse()`` as the portal user, so the
ORM auto-scopes to the user's commercial partner. The controller never reads a
non-whitelisted field, so it can rely on the field-level secrecy too.
"""

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class CustomerPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        """Add the instance count to the portal home cards."""
        values = super()._prepare_home_portal_values(counters)
        if "instance_count" in counters:
            # Record rule scopes the count to the user's own instances.
            values["instance_count"] = request.env[
                "k8s.odoo.instance"
            ].search_count([])
        return values

    @http.route(["/my/instances"], type="http", auth="user", website=True)
    def portal_my_instances(self, **kw):
        """List the user's instances grouped into Production and Staging.

        The Feature A record rule auto-scopes ``search([])`` to the portal
        user's owned instances, so no manual partner filter is needed.
        """
        Instance = request.env["k8s.odoo.instance"]
        instances = Instance.search([])
        production = instances.filtered(
            lambda inst: inst.environment == "production"
        )
        staging = instances.filtered(
            lambda inst: inst.environment == "staging"
        )
        values = {
            "page_name": "instances",
            "production_instances": production,
            "staging_instances": staging,
            "default_url": "/my/instances",
        }
        return request.render(
            "odoo_herd_portal.portal_my_instances", values
        )

    @http.route(
        ["/my/instances/<int:instance_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_instance_detail(self, instance_id, access_token=None, **kw):
        """Render the detail page for one owned instance.

        Uses the standard ``_document_check_access`` pattern: a foreign or
        non-existent instance raises ``AccessError`` / ``MissingError`` (the
        record rule empties/denies it), which we map to a redirect to the
        instances list rather than leaking any data.
        """
        try:
            instance_sudo = self._document_check_access(
                "k8s.odoo.instance", instance_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my/instances")
        values = {
            "page_name": "instance_detail",
            "instance": instance_sudo,
        }
        return request.render(
            "odoo_herd_portal.portal_instance_detail", values
        )
