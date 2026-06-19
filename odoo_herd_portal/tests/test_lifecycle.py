# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature E -- self-serve lifecycle acceptance tests (upgrade + staging-refresh).

Acceptance criteria under test:

* (a) Upgrade on an OWNED instance creates a ``k8s.odoo.upgrade`` job AND a
  PRECEDING ``k8s.odoo.backup`` (the auto-backup-before-upgrade guardrail). The
  same POST on a NON-owned instance creates nothing -- no upgrade, no backup,
  and the k8s CR hooks are never called (IDOR protection).
* (b) Safe-target guardrail: a portal-supplied ``modules_install`` (or any
  arbitrary module list in the request) NEVER reaches the upgrade job / k8s
  call. The upgrade is the instance's STANDARD upgrade, derived server-side.
* (c) Staging-refresh is ALLOWED when the target is a staging instance the user
  owns whose ``production_instance_id`` they also own; it is REFUSED when the
  target is production (the control is never exposed there); REFUSED for a
  non-owned target (IDOR); and the created refresh is bound to the correct
  source = the target's ``production_instance_id``.
* (d) A sensitive field on ``k8s.odoo.upgrade`` / ``k8s.odoo.staging.refresh``
  (webhook token, job names/uids, internal refs) raises AccessError for a
  portal user even via the ORM (deny-by-default field whitelist). A drift-guard
  ensures any field NOT whitelisted stays hidden, for BOTH models.
* (e) Every client-initiated action (upgrade, staging-refresh) posts an audit
  chatter message on the instance recording who/what/when.
* (f) The client-completion/failure notification is created on a SIMULATED
  terminal-state transition (the operator webhook drives ``mark_completed`` /
  ``mark_failed`` in prod): a message is posted to the instance's chatter.

These mix HttpCase (end-to-end controller + record rule + CSRF) and
TransactionCase (ORM-level field secrecy / drift-guard / notification hook).
The actual Kubernetes calls are stubbed by patching each job model's CR-creation
hook, mirroring Feature D's tests and how ``odoo_herd``'s own tests avoid a live
cluster.
"""

from unittest.mock import patch

from odoo import http
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.odoo_herd_portal.models.k8s_odoo_upgrade import (
    PORTAL_VISIBLE_UPGRADE_FIELDS,
)
from odoo.addons.odoo_herd_portal.models.k8s_odoo_staging_refresh import (
    PORTAL_VISIBLE_REFRESH_FIELDS,
)

# CR-creation hooks that hit the live cluster; stubbed in every test that
# creates a job record so no Kubernetes API call is made.
_BACKUP_CR = (
    "odoo.addons.odoo_herd.models.k8s_backup.K8sOdooBackup._create_backup_job_cr"
)
_UPGRADE_CR = (
    "odoo.addons.odoo_herd.models.k8s_upgrade.K8sOdooUpgrade._trigger_upgrade"
)
_REFRESH_CR = (
    "odoo.addons.odoo_herd.models.k8s_staging_refresh"
    ".K8sOdooStagingRefresh._create_refresh_job_cr"
)

# Framework / audit fields readable by any user by design -- excluded from the
# drift-guard (same rationale as Feature A/D drift-guards).
_FRAMEWORK_READABLE = frozenset(
    {
        "create_date",
        "write_date",
        "create_uid",
        "write_uid",
        "__last_update",
    }
)


def _common_fixtures(cls):
    """Build the two-company / instances fixture set for lifecycle tests."""
    Partner = cls.env["res.partner"]
    Users = cls.env["res.users"]
    portal_group = cls.env.ref("base.group_portal")

    cls.company_a = Partner.create({"name": "Life Co A", "is_company": True})
    cls.company_b = Partner.create({"name": "Life Co B", "is_company": True})

    # A portal *initiator* contact under company A, distinct from the company
    # partner itself. Used to assert the terminal notification targets the
    # acting initiator -- NOT every allowed_partner_ids member (the company).
    cls.initiator_a = Partner.create(
        {
            "name": "Life Initiator A",
            "email": "initiator_a@example.com",
            "parent_id": cls.company_a.id,
        }
    )

    cls.user_a = Users.create(
        {
            "name": "Life User A",
            "login": "life_user_a",
            "password": "life_user_a",
            "email": "life_a@example.com",
            "partner_id": cls.company_a.id,
            "group_ids": [(6, 0, [portal_group.id])],
        }
    )
    cls.user_b = Users.create(
        {
            "name": "Life User B",
            "login": "life_user_b",
            "password": "life_user_b",
            "email": "life_b@example.com",
            "partner_id": cls.company_b.id,
            "group_ids": [(6, 0, [portal_group.id])],
        }
    )

    cls.s3_config = cls.env["k8s.s3.config"].create(
        {
            "name": "Life Test S3",
            "endpoint": "https://minio.invalid",
            "bucket": "backups",
            "credentials_secret_name": "s3-creds",
        }
    )
    # Active cluster: the upgrade/refresh wizard pre-flight checks
    # ``cluster_id.active``; CR hooks are stubbed so no real call is made.
    cls.cluster = cls.env["k8s.cluster"].create(
        {
            "name": "Life Test Cluster",
            "api_endpoint": "https://example.invalid:6443",
            "kubeconfig": "apiVersion: v1\nkind: Config\n",
            "default_namespace": "default",
            "active": True,
            "backup_s3_config_id": cls.s3_config.id,
        }
    )

    Instance = cls.env["k8s.odoo.instance"]
    # Company A: production + staging (staging sourced from prod).
    cls.inst_a_prod = Instance.create(
        {
            "name": "lifeco-a-prod",
            "namespace": "lifeco-a",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
        }
    )
    cls.inst_a_staging = Instance.create(
        {
            "name": "lifeco-a-staging",
            "namespace": "lifeco-a",
            "cluster_id": cls.cluster.id,
            "environment": "staging",
            "production_instance_id": cls.inst_a_prod.id,
            "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
        }
    )
    # Company B: a production instance, never visible to A.
    cls.inst_b_prod = Instance.create(
        {
            "name": "lifeco-b-prod",
            "namespace": "lifeco-b",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_b.id])],
        }
    )
    cls.inst_b_staging = Instance.create(
        {
            "name": "lifeco-b-staging",
            "namespace": "lifeco-b",
            "cluster_id": cls.cluster.id,
            "environment": "staging",
            "production_instance_id": cls.inst_b_prod.id,
            "allowed_partner_ids": [(6, 0, [cls.company_b.id])],
        }
    )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLifecycleSecrecy(TransactionCase):
    """ORM-level field secrecy + drift-guard for both job models (d)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)
        # One upgrade + one refresh job to read fields off, created with the
        # CR hooks stubbed so no cluster call is made.
        with patch(_UPGRADE_CR):
            cls.upgrade = cls.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": cls.inst_a_prod.id,
                    "modules": "base",
                }
            )
        with patch(_REFRESH_CR):
            cls.refresh = cls.env["k8s.odoo.staging.refresh"].create(
                {
                    "target_instance_id": cls.inst_a_staging.id,
                    "source_instance_id": cls.inst_a_prod.id,
                }
            )

    # -------------------------------------------------------------- (d) upgrade
    def test_sensitive_upgrade_fields_hidden(self):
        """Known secret upgrade fields raise AccessError for a portal user."""
        rec = self.upgrade.with_user(self.user_a)
        for field_name in ("webhook_token", "job_name", "job_uid", "message"):
            with self.subTest(field=field_name):
                with self.assertRaises(AccessError), mute_logger("odoo.models"):
                    rec.read([field_name])

    def test_whitelisted_upgrade_fields_readable(self):
        """Every whitelisted upgrade field stays readable by a portal user."""
        rec = self.upgrade.with_user(self.user_a)
        model_fields = self.env["k8s.odoo.upgrade"]._fields
        readable = sorted(PORTAL_VISIBLE_UPGRADE_FIELDS & set(model_fields))
        self.assertEqual(
            set(readable),
            PORTAL_VISIBLE_UPGRADE_FIELDS,
            "PORTAL_VISIBLE_UPGRADE_FIELDS references fields absent from model.",
        )
        self.assertTrue(rec.read(readable))

    def test_drift_guard_non_whitelisted_upgrade_fields_hidden(self):
        """Deny-by-default: any non-whitelisted upgrade field is hidden."""
        Upgrade = self.env["k8s.odoo.upgrade"]
        rec = self.upgrade.with_user(self.user_a)
        leaked = []
        for field_name in Upgrade._fields:
            if field_name in PORTAL_VISIBLE_UPGRADE_FIELDS:
                continue
            if field_name in _FRAMEWORK_READABLE:
                continue
            with self.subTest(field=field_name):
                try:
                    with mute_logger("odoo.models"):
                        rec.read([field_name])
                except AccessError:
                    continue
                leaked.append(field_name)
        self.assertEqual(
            leaked,
            [],
            "Non-whitelisted upgrade fields readable by a portal user "
            "(add groups= or extend the whitelist): %s" % leaked,
        )

    # -------------------------------------------------------------- (d) refresh
    def test_sensitive_refresh_fields_hidden(self):
        """Known secret staging-refresh fields raise AccessError."""
        rec = self.refresh.with_user(self.user_a)
        for field_name in (
            "webhook_token",
            "refresh_job_name",
            "db_job_name",
            "filestore_job_name",
            "neutralize_job_name",
            "temp_db_name",
            "source_snapshot",
            "rollback_snapshot",
            "message",
        ):
            with self.subTest(field=field_name):
                with self.assertRaises(AccessError), mute_logger("odoo.models"):
                    rec.read([field_name])

    def test_whitelisted_refresh_fields_readable(self):
        """Every whitelisted refresh field stays readable by a portal user."""
        rec = self.refresh.with_user(self.user_a)
        model_fields = self.env["k8s.odoo.staging.refresh"]._fields
        readable = sorted(PORTAL_VISIBLE_REFRESH_FIELDS & set(model_fields))
        self.assertEqual(
            set(readable),
            PORTAL_VISIBLE_REFRESH_FIELDS,
            "PORTAL_VISIBLE_REFRESH_FIELDS references fields absent from model.",
        )
        self.assertTrue(rec.read(readable))

    def test_drift_guard_non_whitelisted_refresh_fields_hidden(self):
        """Deny-by-default: any non-whitelisted refresh field is hidden."""
        Refresh = self.env["k8s.odoo.staging.refresh"]
        rec = self.refresh.with_user(self.user_a)
        leaked = []
        for field_name in Refresh._fields:
            if field_name in PORTAL_VISIBLE_REFRESH_FIELDS:
                continue
            if field_name in _FRAMEWORK_READABLE:
                continue
            with self.subTest(field=field_name):
                try:
                    with mute_logger("odoo.models"):
                        rec.read([field_name])
                except AccessError:
                    continue
                leaked.append(field_name)
        self.assertEqual(
            leaked,
            [],
            "Non-whitelisted refresh fields readable by a portal user "
            "(add groups= or extend the whitelist): %s" % leaked,
        )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLifecycleNotification(TransactionCase):
    """Client completion/failure notification on terminal-state transition (f)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    def _new_messages(self, instance, before_ids):
        """Return messages posted on ``instance`` since the ``before_ids`` set."""
        instance.invalidate_recordset()
        return instance.message_ids.filtered(lambda m: m.id not in before_ids)

    def _assert_client_comment(
        self,
        message,
        initiator_partner,
        body_must_avoid=(),
        not_recipient=(),
        followers=(),
    ):
        """AC (f): the terminal message must reach the client via a client-visible
        comment subtype, NOT an internal note, and must not leak internal detail.

        Targeting rule (Marc's decision): direct recipients are the recorded
        ``portal_initiator_id`` only -- NOT every ``allowed_partner_ids`` member.
        Existing followers are reached via the ``mail.mt_comment`` subtype, not
        by being added to ``partner_ids``.
        """
        self.assertTrue(message, "A terminal notification must be posted.")
        self.assertEqual(
            len(message),
            1,
            "Exactly one terminal client comment is expected, got %s." % len(message),
        )
        comment_subtype = self.env.ref("mail.mt_comment")
        note_subtype = self.env.ref("mail.mt_note")
        self.assertEqual(
            message.subtype_id,
            comment_subtype,
            "Terminal client notification must use mail.mt_comment "
            "(portal/share-visible), not an internal note.",
        )
        self.assertNotEqual(
            message.subtype_id,
            note_subtype,
            "Terminal client notification must NOT be an internal mt_note.",
        )
        if initiator_partner is not None:
            self.assertIn(
                initiator_partner,
                message.partner_ids,
                "The recorded portal initiator must be a direct recipient of "
                "the terminal notification.",
            )
        for partner in not_recipient:
            self.assertNotIn(
                partner,
                message.partner_ids,
                "A non-initiator allowed partner must NOT be a direct recipient "
                "(no all-allowed-partners blast).",
            )
        for follower in followers:
            self.assertIn(
                follower,
                message.notified_partner_ids,
                "An existing follower must be notified by the mt_comment subtype.",
            )
        for forbidden in body_must_avoid:
            self.assertNotIn(
                forbidden,
                message.body or "",
                "Client-facing body must be status-only; it leaked the raw "
                "operator message %r." % forbidden,
            )

    def test_upgrade_completion_notifies_initiator(self):
        """mark_completed posts a client-visible comment to the initiator only."""
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "modules": "base",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_prod.message_ids.ids)
        upgrade.mark_completed(message="INTERNAL: /var/lib/odoo trace")
        new = self._new_messages(self.inst_a_prod, before)
        self._assert_client_comment(
            new,
            self.initiator_a,
            body_must_avoid=("INTERNAL: /var/lib/odoo trace",),
            # The bare allowed-partner (company) is NOT a follower and NOT the
            # initiator, so it must not be a direct recipient.
            not_recipient=(self.company_a,),
        )

    def test_upgrade_failure_notifies_initiator(self):
        """mark_failed posts a client-visible comment to the initiator only."""
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "modules": "base",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_prod.message_ids.ids)
        upgrade.mark_failed(message="INTERNAL: boom at /opt/odoo")
        new = self._new_messages(self.inst_a_prod, before)
        self._assert_client_comment(
            new,
            self.initiator_a,
            body_must_avoid=("INTERNAL: boom at /opt/odoo",),
            not_recipient=(self.company_a,),
        )

    def test_refresh_completion_notifies_initiator(self):
        """mark_completed on a refresh comments the recorded initiator only."""
        with patch(_REFRESH_CR):
            refresh = self.env["k8s.odoo.staging.refresh"].create(
                {
                    "target_instance_id": self.inst_a_staging.id,
                    "source_instance_id": self.inst_a_prod.id,
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_staging.message_ids.ids)
        refresh.mark_completed(message="INTERNAL: snapshot detail")
        new = self._new_messages(self.inst_a_staging, before)
        self._assert_client_comment(
            new,
            self.initiator_a,
            body_must_avoid=("INTERNAL: snapshot detail",),
            not_recipient=(self.company_a,),
        )

    def test_backup_completion_notifies_initiator(self):
        """mark_completed on a backup comments the recorded initiator only."""
        with patch(_BACKUP_CR):
            backup = self.env["k8s.odoo.backup"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "format": "zip",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_prod.message_ids.ids)
        backup.mark_completed(message="INTERNAL: object_key s3://x")
        new = self._new_messages(self.inst_a_prod, before)
        self._assert_client_comment(
            new,
            self.initiator_a,
            body_must_avoid=("INTERNAL: object_key s3://x",),
            not_recipient=(self.company_a,),
        )

    def test_terminal_notification_notifies_followers(self):
        """An existing follower is notified via the mt_comment subtype."""
        # Subscribe a follower partner BEFORE the terminal transition.
        follower = self.env["res.partner"].create(
            {"name": "Life Follower", "email": "follower@example.com"}
        )
        self.inst_a_prod.message_subscribe(partner_ids=follower.ids)
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "modules": "base",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_prod.message_ids.ids)
        upgrade.mark_completed(message="done")
        new = self._new_messages(self.inst_a_prod, before)
        self._assert_client_comment(
            new,
            self.initiator_a,
            followers=(follower,),
            not_recipient=(self.company_a,),
        )

    def test_terminal_notification_without_initiator_notifies_followers_only(self):
        """Herd/operator-driven op (no initiator): followers only, no direct partner."""
        follower = self.env["res.partner"].create(
            {"name": "Life Follower 2", "email": "follower2@example.com"}
        )
        self.inst_a_prod.message_subscribe(partner_ids=follower.ids)
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {"instance_id": self.inst_a_prod.id, "modules": "base"}
            )
        before = set(self.inst_a_prod.message_ids.ids)
        upgrade.mark_completed(message="done")
        new = self._new_messages(self.inst_a_prod, before)
        # No initiator => no direct partner_ids recipient at all.
        self._assert_client_comment(
            new,
            None,
            followers=(follower,),
            not_recipient=(self.company_a,),
        )
        self.assertFalse(
            new.partner_ids,
            "With no portal initiator there must be no direct partner_ids "
            "recipient (followers are reached via the subtype).",
        )

    def test_terminal_notification_excludes_non_allowed_partner(self):
        """Negative: a non-allowed company's partner is NOT a recipient."""
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "modules": "base",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        before = set(self.inst_a_prod.message_ids.ids)
        upgrade.mark_completed(message="done")
        new = self._new_messages(self.inst_a_prod, before)
        self.assertTrue(new, "A terminal notification must be posted.")
        self.assertNotIn(
            self.company_b,
            new.partner_ids,
            "A non-allowed company's partner must NOT receive the "
            "terminal notification.",
        )

    def test_terminal_notification_does_not_subscribe_initiator(self):
        """No auto-subscription: the initiator is not added as a follower."""
        with patch(_UPGRADE_CR):
            upgrade = self.env["k8s.odoo.upgrade"].create(
                {
                    "instance_id": self.inst_a_prod.id,
                    "modules": "base",
                    "portal_initiator_id": self.initiator_a.id,
                }
            )
        upgrade.mark_completed(message="done")
        self.inst_a_prod.invalidate_recordset()
        self.assertNotIn(
            self.initiator_a,
            self.inst_a_prod.message_partner_ids,
            "The terminal notification must NOT subscribe the initiator as a "
            "standing follower.",
        )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLifecycleSelfService(HttpCase):
    """End-to-end controller: upgrade + staging-refresh (a, b, c, e)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    def _csrf_token(self):
        return http.Request.csrf_token(self)

    # ============================================================= (a) upgrade
    def test_upgrade_owned_creates_upgrade_and_backup(self):
        """POST upgrade on an owned instance creates an upgrade + a backup."""
        self.authenticate("life_user_a", "life_user_a")
        Upgrade = self.env["k8s.odoo.upgrade"]
        Backup = self.env["k8s.odoo.backup"]
        up_before = Upgrade.search_count([("instance_id", "=", self.inst_a_prod.id)])
        bk_before = Backup.search_count([("instance_id", "=", self.inst_a_prod.id)])
        with patch(_UPGRADE_CR) as up_cr, patch(_BACKUP_CR) as bk_cr:
            resp = self.url_open(
                "/my/instances/%d/upgrade" % self.inst_a_prod.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.assertEqual(resp.status_code, 200)
        up_after = Upgrade.search_count([("instance_id", "=", self.inst_a_prod.id)])
        bk_after = Backup.search_count([("instance_id", "=", self.inst_a_prod.id)])
        self.assertEqual(up_after, up_before + 1, "An upgrade job must be created.")
        self.assertEqual(
            bk_after, bk_before + 1, "An auto-backup must precede the upgrade."
        )
        self.assertTrue(up_cr.called, "Upgrade CR hook must run under sudo.")
        self.assertTrue(bk_cr.called, "Backup CR hook must run under sudo.")
        # Backup must be created BEFORE the upgrade (guardrail ordering).
        # The two models have independent id sequences, so compare by
        # create_date instead of id.
        backup = Backup.search(
            [("instance_id", "=", self.inst_a_prod.id)],
            order="create_date desc, id desc",
            limit=1,
        )
        upgrade = Upgrade.search(
            [("instance_id", "=", self.inst_a_prod.id)],
            order="create_date desc, id desc",
            limit=1,
        )
        self.assertLessEqual(
            backup.create_date,
            upgrade.create_date,
            "Backup must be created before (or at) the upgrade.",
        )

    def test_upgrade_non_owned_refused(self):
        """POST upgrade on a non-owned instance creates nothing (IDOR)."""
        self.authenticate("life_user_a", "life_user_a")
        Upgrade = self.env["k8s.odoo.upgrade"]
        Backup = self.env["k8s.odoo.backup"]
        up_before = Upgrade.search_count([("instance_id", "=", self.inst_b_prod.id)])
        bk_before = Backup.search_count([("instance_id", "=", self.inst_b_prod.id)])
        with patch(_UPGRADE_CR) as up_cr, patch(_BACKUP_CR) as bk_cr:
            resp = self.url_open(
                "/my/instances/%d/upgrade" % self.inst_b_prod.id,
                data={"csrf_token": self._csrf_token()},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        up_after = Upgrade.search_count([("instance_id", "=", self.inst_b_prod.id)])
        bk_after = Backup.search_count([("instance_id", "=", self.inst_b_prod.id)])
        self.assertEqual(up_after, up_before, "No upgrade for a foreign instance.")
        self.assertEqual(bk_after, bk_before, "No backup for a foreign instance.")
        self.assertFalse(up_cr.called)
        self.assertFalse(bk_cr.called)

    # ============================================================= (b) safe-target
    def test_upgrade_ignores_supplied_module_install_list(self):
        """A portal-supplied modules_install never reaches the upgrade job."""
        self.authenticate("life_user_a", "life_user_a")
        Upgrade = self.env["k8s.odoo.upgrade"]
        with patch(_UPGRADE_CR), patch(_BACKUP_CR):
            self.url_open(
                "/my/instances/%d/upgrade" % self.inst_a_prod.id,
                data={
                    "csrf_token": self._csrf_token(),
                    # Attacker-controlled install-anything vector:
                    "modules_install": "auth_signup,base_import_module",
                    "modules": "account,sale",
                },
            )
        upgrade = Upgrade.search(
            [("instance_id", "=", self.inst_a_prod.id)],
            order="create_date desc, id desc",
            limit=1,
        )
        # Nothing the client sent may end up on the job.
        self.assertFalse(
            upgrade.modules_install,
            "No portal-supplied install list may reach the upgrade job.",
        )
        for forbidden in ("auth_signup", "base_import_module"):
            self.assertNotIn(forbidden, upgrade.modules or "")

    # ============================================================= (c) refresh
    def test_refresh_staging_owned_creates_refresh_bound_to_source(self):
        """Refresh on an owned staging instance creates a refresh from prod."""
        self.authenticate("life_user_a", "life_user_a")
        Refresh = self.env["k8s.odoo.staging.refresh"]
        before = Refresh.search_count([])
        with patch(_REFRESH_CR) as cr:
            resp = self.url_open(
                "/my/instances/%d/refresh-staging" % self.inst_a_staging.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Refresh.search_count([]), before + 1)
        self.assertTrue(cr.called)
        new = Refresh.search([], order="create_date desc, id desc", limit=1)
        self.assertEqual(new.target_instance_id, self.inst_a_staging)
        self.assertEqual(
            new.source_instance_id,
            self.inst_a_prod,
            "Source must be bound to the target's production_instance_id.",
        )

    def test_refresh_production_target_refused(self):
        """Refresh targeting a production instance is refused (never exposed)."""
        self.authenticate("life_user_a", "life_user_a")
        Refresh = self.env["k8s.odoo.staging.refresh"]
        before = Refresh.search_count([])
        with patch(_REFRESH_CR) as cr:
            resp = self.url_open(
                "/my/instances/%d/refresh-staging" % self.inst_a_prod.id,
                data={"csrf_token": self._csrf_token()},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        self.assertEqual(
            Refresh.search_count([]), before, "No refresh against a production target."
        )
        self.assertFalse(cr.called)

    def test_refresh_non_owned_refused(self):
        """Refresh on a non-owned staging instance is refused (IDOR)."""
        self.authenticate("life_user_a", "life_user_a")
        Refresh = self.env["k8s.odoo.staging.refresh"]
        before = Refresh.search_count([])
        with patch(_REFRESH_CR) as cr:
            resp = self.url_open(
                "/my/instances/%d/refresh-staging" % self.inst_b_staging.id,
                data={"csrf_token": self._csrf_token()},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        self.assertEqual(Refresh.search_count([]), before)
        self.assertFalse(cr.called)

    # ============================================================= (e) audit
    def test_upgrade_posts_audit_message(self):
        """Upgrade posts an audit chatter message on the instance."""
        self.authenticate("life_user_a", "life_user_a")
        before = len(self.inst_a_prod.message_ids)
        with patch(_UPGRADE_CR), patch(_BACKUP_CR):
            self.url_open(
                "/my/instances/%d/upgrade" % self.inst_a_prod.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.inst_a_prod.invalidate_recordset()
        messages = self.inst_a_prod.message_ids
        self.assertGreater(len(messages), before)
        bodies = " ".join(m.body or "" for m in messages)
        self.assertIn("pgrade", bodies)
        # Authored by the acting portal user (who/what/when).
        self.assertTrue(
            any(m.author_id == self.user_a.partner_id for m in messages)
        )

    def test_refresh_posts_audit_message(self):
        """Staging-refresh posts an audit chatter message on the target."""
        self.authenticate("life_user_a", "life_user_a")
        before = len(self.inst_a_staging.message_ids)
        with patch(_REFRESH_CR):
            self.url_open(
                "/my/instances/%d/refresh-staging" % self.inst_a_staging.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.inst_a_staging.invalidate_recordset()
        messages = self.inst_a_staging.message_ids
        self.assertGreater(len(messages), before)
        self.assertTrue(
            any(m.author_id == self.user_a.partner_id for m in messages)
        )
