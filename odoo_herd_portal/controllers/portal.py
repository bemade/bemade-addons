# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
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

import logging

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


def _portal_audit(instance, action):
    """Post a lightweight audit message to an instance's chatter.

    Reusable by Feature E (lifecycle actions). ``instance`` is a sudoed
    recordset (chatter posting needs write access the portal user lacks), but
    the author is forced to the *acting* portal user's partner so the chatter
    records WHO performed the action -- ``who/what/when`` per SPEC §5. The body
    states the action came from the self-service portal.
    """
    user = request.env.user
    instance.message_post(
        body=_(
            "Portal self-service action: %(action)s "
            "(initiated by %(user)s via the client portal).",
            action=action,
            user=user.name,
        ),
        author_id=user.partner_id.id,
        message_type="comment",
        subtype_xmlid="mail.mt_note",
    )


def _record_portal_initiator(model_name, instance_id, partner_id):
    """Stamp ``portal_initiator_id`` on the job just created by a wizard.

    The wizard actions (``action_create_backup`` / ``action_upgrade`` /
    ``action_refresh``) return an action dict, not the created job, and we must
    not modify the base ``odoo_herd`` wizards. The job is created synchronously
    in this same transaction, so the most-recent job for ``instance_id`` is the
    one we just triggered; stamp the acting portal user's partner on it so the
    terminal-state notification can address the initiator directly.

    The terminal CR-creation hook fires during ``create`` (before this write),
    so stamping the initiator afterwards is safe. ``instance_field`` differs by
    model (``instance_id`` vs ``target_instance_id``); both are passed by key.
    """
    if not partner_id:
        return
    Job = request.env[model_name].sudo()
    instance_field = (
        "target_instance_id"
        if model_name == "k8s.odoo.staging.refresh"
        else "instance_id"
    )
    job = Job.search(
        [(instance_field, "=", instance_id)],
        order="id desc",
        limit=1,
    )
    if job:
        job.portal_initiator_id = partner_id


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

        ``_document_check_access`` is used ONLY as the access *check*: a foreign
        or non-existent instance raises ``AccessError`` / ``MissingError`` (the
        record rule empties/denies it), which we map to a redirect to the
        instances list rather than leaking any data.

        It returns the record **sudoed**, on which BOTH Feature A's field
        ``groups=`` and the record rule are bypassed. We therefore re-browse the
        record AS THE PORTAL USER for rendering, so the field-level secrecy and
        the record rule are reinstated on the detail page -- the template's
        secrecy no longer hinges on which fields it happens to reference.
        """
        try:
            self._document_check_access(
                "k8s.odoo.instance", instance_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my/instances")
        # Re-browse in the portal user's context (NOT sudo): field groups= and
        # the record rule now apply on the rendered record.
        instance = request.env["k8s.odoo.instance"].browse(instance_id)
        # The source production instance is a cross-record reference that is NOT
        # constrained to share this instance's allowed_partner_ids, so it may be
        # owned by another company. Reading ``.name`` on a non-readable related
        # record raises AccessError under the record rule, so resolve it through
        # an explicit read-access filter and only pass the name when the user
        # may actually read that record. ``name`` (never ``display_name``, which
        # leaks under su/k8s context) is used.
        prod_source_name = False
        prod_source = instance.production_instance_id
        if prod_source and prod_source._filtered_access("read"):
            prod_source_name = prod_source.name
        values = {
            "page_name": "instance_detail",
            "instance": instance,
            "prod_source_name": prod_source_name,
        }
        return request.render(
            "odoo_herd_portal.portal_instance_detail", values
        )

    # ==================================================================
    # Feature C -- live log viewer (token mint + iframe/postMessage handoff)
    # ==================================================================
    # ir.config_parameter key for the sidecar SPA base URL (e.g.
    # ``https://logs.bemade.org``). The token is NEVER placed in this URL.
    _LOG_VIEWER_URL_PARAM = "odoo_herd_portal.log_viewer_url"

    @http.route(
        ["/my/instances/<int:instance_id>/logs"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_instance_logs(self, instance_id, **kw):
        """Render the live log viewer page for one owned instance.

        Ownership is checked AS THE USER first (``_check_instance_access``):
        a foreign/non-existent id yields ``None`` and we redirect WITHOUT
        minting a token (IDOR guard -- no scope token, no namespace leak).

        Only after that check do we mint the short-lived signed scope token
        (``_mint_log_token`` reads the group-hidden namespace/name under sudo).
        The token is handed to the iframe via ``postMessage`` (see the static
        JS asset); it is embedded in a data attribute, NEVER in the iframe
        ``src`` / query string -- so it is not logged by proxies. The signing
        secret never reaches the page.
        """
        instance = self._check_instance_access(instance_id)
        if instance is None:
            return request.redirect("/my/instances")
        # Token mint happens strictly after the ownership check above.
        log_token = instance._mint_log_token()
        viewer_url = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param(self._LOG_VIEWER_URL_PARAM)
            or ""
        )
        values = {
            "page_name": "instance_logs",
            "instance": instance,
            "log_token": log_token,
            "log_viewer_url": viewer_url,
        }
        return request.render(
            "odoo_herd_portal.portal_instance_logs", values
        )

    # ==================================================================
    # Feature D -- backups self-service
    # ==================================================================
    def _check_instance_access(self, instance_id):
        """Return the instance browsed AS THE PORTAL USER, or None.

        The read happens in the user's own env so the Feature A record rule
        applies: a foreign/non-existent id yields an empty/denied recordset and
        we return ``None``. Callers MUST treat ``None`` as "refuse" and only
        escalate to ``sudo()`` once a non-None instance is returned. This is the
        ownership-check-as-user-THEN-sudo pattern that prevents IDOR.
        """
        instance = request.env["k8s.odoo.instance"].browse(instance_id)
        try:
            if not instance.exists() or not instance._filtered_access("read"):
                return None
        except (AccessError, MissingError):
            return None
        return instance

    def _check_backup_access(self, backup_id):
        """Return the backup browsed AS THE PORTAL USER, or None (refuse)."""
        backup = request.env["k8s.odoo.backup"].browse(backup_id)
        try:
            if not backup.exists() or not backup._filtered_access("read"):
                return None
        except (AccessError, MissingError):
            return None
        return backup

    @http.route(
        ["/my/instances/<int:instance_id>/backups"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_instance_backups(self, instance_id, **kw):
        """List the backups of one owned instance (whitelisted fields only).

        The backup record rule auto-scopes ``search`` to backups whose instance
        the user owns; we additionally constrain to this instance.
        """
        instance = self._check_instance_access(instance_id)
        if instance is None:
            return request.redirect("/my/instances")
        backups = request.env["k8s.odoo.backup"].search(
            [("instance_id", "=", instance.id)]
        )
        values = {
            "page_name": "instance_backups",
            "instance": instance,
            "backups": backups,
            "default_url": "/my/instances/%d/backups" % instance.id,
        }
        return request.render(
            "odoo_herd_portal.portal_instance_backups", values
        )

    @http.route(
        ["/my/instances/<int:instance_id>/backup"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_instance_backup_now(self, instance_id, **post):
        """Trigger a new backup for an owned instance (CSRF-protected POST).

        Ownership is checked AS THE USER first; only then do we reuse the
        existing k8s.backup.wizard logic under ``sudo()``. A non-owned instance
        id is refused without creating anything (IDOR protection).
        """
        instance = self._check_instance_access(instance_id)
        if instance is None:
            return request.redirect("/my/instances")
        # Capture the acting portal user's partner BEFORE escalating to sudo.
        initiator_partner_id = request.env.user.partner_id.id
        fmt = post.get("format") or "zip"
        if fmt not in ("zip", "dump", "sql"):
            fmt = "zip"
        try:
            wizard = (
                request.env["k8s.backup.wizard"]
                .sudo()
                .create(
                    {
                        "instance_id": instance.id,
                        "format": fmt,
                        "with_filestore": fmt == "zip",
                    }
                )
            )
            wizard.action_create_backup()
            _record_portal_initiator(
                "k8s.odoo.backup", instance.id, initiator_partner_id
            )
            # Audit on the sudoed instance, authored by the portal user.
            _portal_audit(
                instance.sudo(),
                _("Backup requested (format %s)") % fmt.upper(),
            )
        except (UserError, AccessError) as exc:
            _logger.warning(
                "Portal backup-now failed for instance %s: %s",
                instance_id,
                exc,
            )
            return request.redirect(
                "/my/instances/%d/backups?error=backup" % instance_id
            )
        return request.redirect("/my/instances/%d/backups" % instance_id)

    @http.route(
        ["/my/instances/backup/<int:backup_id>/restore"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_backup_restore(self, backup_id, **post):
        """Restore a backup onto its instance -- STAGING ONLY (CSRF POST).

        Ownership of the backup is checked AS THE USER; then the TARGET
        instance's environment must be ``staging`` -- a production target is
        refused outright (never exposed). On staging, the existing
        k8s.restore.backup.wizard flow is reused under ``sudo()``.
        """
        backup = self._check_backup_access(backup_id)
        if backup is None:
            return request.redirect("/my/instances")
        # Re-derive the target instance via an owned read (record rule applies).
        target = self._check_instance_access(backup.instance_id.id)
        if target is None:
            return request.redirect("/my/instances")
        # Environment gate: production restore is NEVER self-service.
        if target.environment != "staging":
            _logger.warning(
                "Portal restore refused: target instance %s is not staging.",
                target.id,
            )
            return request.redirect(
                "/my/instances/%d/backups?error=prod_restore" % target.id
            )
        try:
            wizard = (
                request.env["k8s.restore.backup.wizard"]
                .sudo()
                .create(
                    {
                        "backup_id": backup.id,
                        "target_instance_id": target.id,
                        "confirmation_name": target.sudo().name,
                    }
                )
            )
            wizard.action_restore()
            _portal_audit(
                target.sudo(),
                _("Staging restore from backup %s") % backup.sudo().name,
            )
        except (UserError, AccessError) as exc:
            _logger.warning(
                "Portal restore failed for backup %s: %s", backup_id, exc
            )
            return request.redirect(
                "/my/instances/%d/backups?error=restore" % target.id
            )
        return request.redirect("/my/instances/%d/backups" % target.id)

    # ==================================================================
    # Feature E -- self-serve lifecycle (upgrade + staging-refresh)
    # ==================================================================
    # The portal triggers the instance's STANDARD upgrade: ``odoo -u all``
    # (upgrade every already-installed module). The module list is a
    # SERVER-FIXED constant, never derived from the request, so the portal can
    # never be used as an install-anything vector (no modules_install reaches
    # the k8s call). See the "safe targets" decision in the module docs.
    _UPGRADE_STANDARD_MODULES = "all"

    @http.route(
        ["/my/instances/<int:instance_id>/upgrade"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_instance_upgrade(self, instance_id, **post):
        """Trigger the instance's STANDARD upgrade (CSRF-protected POST).

        Guardrails:

        * Ownership is checked AS THE USER first; a non-owned instance id is
          refused without creating anything (IDOR protection).
        * **Auto-backup first:** a backup of the instance is created (reusing
          Feature D's k8s.backup.wizard path) BEFORE the upgrade, so the upgrade
          always follows a fresh backup.
        * **Safe target only:** the upgrade module list is the server-fixed
          ``_UPGRADE_STANDARD_MODULES`` constant; NOTHING from the request body
          reaches the upgrade job. ``modules_install`` is always empty.

        Only after the ownership check do we escalate to ``sudo()`` to reuse the
        existing wizard/job pipeline (we never reimplement the k8s call).
        """
        instance = self._check_instance_access(instance_id)
        if instance is None:
            return request.redirect("/my/instances")
        # Capture the acting portal user's partner BEFORE escalating to sudo.
        initiator_partner_id = request.env.user.partner_id.id
        try:
            sudo_instance = instance.sudo()
            # GUARDRAIL 1 -- auto-backup BEFORE the upgrade.
            backup_wizard = (
                request.env["k8s.backup.wizard"]
                .sudo()
                .create(
                    {
                        "instance_id": instance.id,
                        "format": "zip",
                        "with_filestore": True,
                    }
                )
            )
            backup_wizard.action_create_backup()
            # NOTE: the pre-upgrade guardrail backup is deliberately NOT stamped
            # with portal_initiator_id. It is an internal guardrail, not a
            # user-requested "Backup now", so it must stay silent -- only the
            # upgrade job (stamped below) notifies the initiator. Stamping it
            # would double-notify for a single user action.
            # GUARDRAIL 2 -- standard upgrade, server-fixed module list only.
            upgrade_wizard = (
                request.env["k8s.upgrade.wizard"]
                .sudo()
                .create(
                    {
                        "instance_id": instance.id,
                        "modules": self._UPGRADE_STANDARD_MODULES,
                        "modules_install": "",
                    }
                )
            )
            upgrade_wizard.action_upgrade()
            _record_portal_initiator(
                "k8s.odoo.upgrade", instance.id, initiator_partner_id
            )
            _portal_audit(
                sudo_instance,
                _("Module upgrade (standard, after auto-backup)"),
            )
        except (UserError, AccessError) as exc:
            _logger.warning(
                "Portal upgrade failed for instance %s: %s", instance_id, exc
            )
            return request.redirect(
                "/my/instances/%d?error=upgrade" % instance_id
            )
        return request.redirect("/my/instances/%d" % instance_id)

    @http.route(
        ["/my/instances/<int:instance_id>/refresh-staging"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_instance_refresh_staging(self, instance_id, **post):
        """Refresh a staging instance from its prod source (CSRF POST).

        Valid ONLY when the target is a staging instance the user owns AND it
        has a ``production_instance_id`` the user also owns. The target's
        ``environment == 'staging'`` is asserted server-side: a production
        target is refused outright (the control is never exposed on production).
        Source is bound server-side to ``production_instance_id`` -- never from
        the request. Ownership of BOTH target and source is checked as the user
        before escalating to ``sudo()`` to reuse the existing refresh wizard.
        """
        target = self._check_instance_access(instance_id)
        if target is None:
            return request.redirect("/my/instances")
        # Environment gate: staging refresh is NEVER offered on production.
        if target.environment != "staging":
            _logger.warning(
                "Portal staging-refresh refused: instance %s is not staging.",
                target.id,
            )
            return request.redirect(
                "/my/instances/%d?error=not_staging" % target.id
            )
        # Source is the configured production_instance_id; ownership-check it AS
        # THE USER too (it may belong to another company).
        source = self._check_instance_access(target.production_instance_id.id)
        if source is None:
            _logger.warning(
                "Portal staging-refresh refused: no owned production source "
                "for instance %s.",
                target.id,
            )
            return request.redirect(
                "/my/instances/%d?error=no_source" % target.id
            )
        # Capture the acting portal user's partner BEFORE escalating to sudo.
        initiator_partner_id = request.env.user.partner_id.id
        try:
            sudo_target = target.sudo()
            wizard = (
                request.env["k8s.staging.refresh.wizard"]
                .sudo()
                .create(
                    {
                        "target_instance_id": target.id,
                        "source_instance_id": source.id,
                        "confirmation_name": sudo_target.name,
                    }
                )
            )
            wizard.action_refresh()
            _record_portal_initiator(
                "k8s.odoo.staging.refresh", target.id, initiator_partner_id
            )
            _portal_audit(
                sudo_target,
                _("Staging refresh from %s") % source.sudo().name,
            )
        except (UserError, AccessError) as exc:
            _logger.warning(
                "Portal staging-refresh failed for instance %s: %s",
                instance_id,
                exc,
            )
            return request.redirect(
                "/my/instances/%d?error=refresh" % target.id
            )
        return request.redirect("/my/instances/%d" % target.id)

    @http.route(
        ["/my/instances/backup/<int:backup_id>/download"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_backup_download(self, backup_id, **kw):
        """Redirect to a fresh S3 pre-signed URL for an owned backup.

        Ownership is checked AS THE USER first; only then, under ``sudo()``, is
        a pre-signed URL generated (reading S3 creds from the cluster secret).
        Portal users NEVER read the S3 credentials or the stored download_url --
        the presign is minted server-side and only the resulting URL is exposed
        via a redirect. A non-owned backup id is refused (no presign).
        """
        backup = self._check_backup_access(backup_id)
        if backup is None:
            return request.redirect("/my/instances")
        if backup.state != "completed":
            return request.redirect(
                "/my/instances/%d/backups?error=not_ready"
                % backup.instance_id.id
            )
        try:
            url = backup.sudo()._generate_presigned_url()
        except (UserError, AccessError) as exc:
            _logger.warning(
                "Portal download presign failed for backup %s: %s",
                backup_id,
                exc,
            )
            return request.redirect(
                "/my/instances/%d/backups?error=download"
                % backup.instance_id.id
            )
        # local=False: the presigned URL is an external S3/MinIO endpoint, so
        # the host must be preserved (the default local=True would strip it).
        return request.redirect(url, local=False)
