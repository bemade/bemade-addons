# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Feature D -- backups self-service acceptance tests.

Acceptance criteria under test:

* (a) A portal user sees ONLY the backups of an instance their company owns;
  another company's backups are invisible at the ORM layer (record rule scoped
  to ``base.group_portal`` via ``instance_id.allowed_partner_ids``).
* (b) Sensitive backup fields (``webhook_token``, ``download_url``, ``job_name``,
  ``backup_job_name``, S3/cluster internals) raise AccessError for a portal
  user even via the ORM (deny-by-default field whitelist). A drift-guard
  ensures any field NOT whitelisted stays hidden.
* (c) "Backup now" creates a new pending ``k8s.odoo.backup`` for an OWNED
  instance (the k8s CR creation is stubbed -- no live cluster), and is REFUSED
  (no record created, redirect/403) for a NON-owned instance (IDOR).
* (d) Restore is ALLOWED (creates a ``k8s.odoo.restore``) when the target
  instance is staging + owned; REFUSED when the target is production (never
  exposed in the portal); and REFUSED for a NON-owned backup (IDOR).
* (e) The download endpoint checks ownership: a non-owned backup id yields a
  redirect/403 and NO presigned URL is leaked; S3 credentials are never read in
  the portal user's context.
* (f) Every client-initiated action (backup-now, restore) posts an audit
  message to the instance's chatter recording who/what/when.

These mix HttpCase (end-to-end controller + record rule + CSRF) and
TransactionCase (ORM-level field secrecy / drift-guard). The actual Kubernetes
calls are stubbed by patching the record models' CR-creation hooks and the
presign method, mirroring how ``odoo_herd``'s own tests avoid a live cluster.
"""

from unittest.mock import patch

from odoo import http
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.odoo_herd_portal.models.k8s_odoo_backup import (
    PORTAL_VISIBLE_BACKUP_FIELDS,
)

# CR-creation hooks that hit the live cluster; stubbed in every test that
# creates a backup or restore record so no Kubernetes API call is made.
_BACKUP_CR = (
    "odoo.addons.odoo_herd.models.k8s_backup.K8sOdooBackup._create_backup_job_cr"
)
_RESTORE_CR = (
    "odoo.addons.odoo_herd.models.k8s_restore.K8sOdooRestore._create_restore_job_cr"
)
_PRESIGN = (
    "odoo.addons.odoo_herd.models.k8s_backup.K8sOdooBackup._generate_presigned_url"
)

# Framework / audit fields readable by any user by design -- excluded from the
# drift-guard (same rationale as Feature A's instance drift-guard).
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
    """Build the two-company / two-instance / backups fixture set."""
    Partner = cls.env["res.partner"]
    Users = cls.env["res.users"]
    portal_group = cls.env.ref("base.group_portal")

    cls.company_a = Partner.create({"name": "Backup Co A", "is_company": True})
    cls.company_b = Partner.create({"name": "Backup Co B", "is_company": True})

    cls.user_a = Users.create(
        {
            "name": "Backup User A",
            "login": "backup_user_a",
            "password": "backup_user_a",
            "email": "backup_a@example.com",
            "partner_id": cls.company_a.id,
            "group_ids": [(6, 0, [portal_group.id])],
        }
    )
    cls.user_b = Users.create(
        {
            "name": "Backup User B",
            "login": "backup_user_b",
            "password": "backup_user_b",
            "email": "backup_b@example.com",
            "partner_id": cls.company_b.id,
            "group_ids": [(6, 0, [portal_group.id])],
        }
    )

    # S3 config so the backup wizard's pre-flight check passes; the real S3
    # call never happens because the CR-creation hooks are stubbed.
    cls.s3_config = cls.env["k8s.s3.config"].create(
        {
            "name": "Test S3",
            "endpoint": "https://minio.invalid",
            "bucket": "backups",
            "credentials_secret_name": "s3-creds",
        }
    )
    # Inactive cluster -- never reached because CR hooks are stubbed, but kept
    # consistent with the rest of the module's fixtures.
    cls.cluster = cls.env["k8s.cluster"].create(
        {
            "name": "Backup Test Cluster",
            "api_endpoint": "https://example.invalid:6443",
            "kubeconfig": "apiVersion: v1\nkind: Config\n",
            "default_namespace": "default",
            "active": False,
            "backup_s3_config_id": cls.s3_config.id,
        }
    )

    Instance = cls.env["k8s.odoo.instance"]
    # Company A: a production + a staging instance.
    cls.inst_a_prod = Instance.create(
        {
            "name": "co-a-prod",
            "namespace": "co-a",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
        }
    )
    cls.inst_a_staging = Instance.create(
        {
            "name": "co-a-staging",
            "namespace": "co-a",
            "cluster_id": cls.cluster.id,
            "environment": "staging",
            "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
        }
    )
    # Company B: a production instance, never visible to A.
    cls.inst_b_prod = Instance.create(
        {
            "name": "co-b-prod",
            "namespace": "co-b",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_b.id])],
        }
    )

    Backup = cls.env["k8s.odoo.backup"]
    with patch(_BACKUP_CR):
        # A completed backup for A's production instance (downloadable).
        cls.backup_a_prod = Backup.create(
            {
                "instance_id": cls.inst_a_prod.id,
                "format": "zip",
                "state": "completed",
                "object_key": "co-a-prod/20260101-000000.zip",
                "bucket": "backups",
                "endpoint": "https://minio.invalid",
                "webhook_token": "SECRET-TOKEN-A",
                "download_url": "https://leak.invalid/presigned-A",
                "size_bytes": 12345,
            }
        )
        # A completed backup for A's staging instance (restore target).
        cls.backup_a_staging = Backup.create(
            {
                "instance_id": cls.inst_a_staging.id,
                "format": "zip",
                "state": "completed",
                "object_key": "co-a-staging/20260101-000000.zip",
                "bucket": "backups",
                "endpoint": "https://minio.invalid",
            }
        )
        # A completed backup for B's production instance -- never visible to A.
        cls.backup_b_prod = Backup.create(
            {
                "instance_id": cls.inst_b_prod.id,
                "format": "zip",
                "state": "completed",
                "object_key": "co-b-prod/20260101-000000.zip",
                "bucket": "backups",
                "endpoint": "https://minio.invalid",
                "webhook_token": "SECRET-TOKEN-B",
            }
        )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestBackupSecrecy(TransactionCase):
    """ORM-level field secrecy + isolation + drift-guard (b, a)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    # -------------------------------------------------------------- (a)
    def test_portal_user_sees_only_own_backups(self):
        """Portal user A sees A's backups; B's backup is invisible."""
        visible = self.env["k8s.odoo.backup"].with_user(self.user_a).search([])
        self.assertIn(self.backup_a_prod, visible)
        self.assertIn(self.backup_a_staging, visible)
        self.assertNotIn(self.backup_b_prod, visible)

    def test_portal_user_cannot_read_other_company_backup(self):
        """Reading B's backup as A raises AccessError (record rule)."""
        with self.assertRaises(AccessError), mute_logger(
            "odoo.addons.base.models.ir_rule"
        ):
            self.backup_b_prod.with_user(self.user_a).read(["name"])

    # -------------------------------------------------------------- (b)
    def test_sensitive_backup_fields_hidden(self):
        """Known secret fields raise AccessError for a portal user."""
        rec = self.backup_a_prod.with_user(self.user_a)
        for field_name in (
            "webhook_token",
            "download_url",
            "job_name",
            "backup_job_name",
            "object_key",
            "bucket",
            "endpoint",
            "cluster_id",
            "s3_config_id",
        ):
            with self.subTest(field=field_name):
                with self.assertRaises(AccessError), mute_logger("odoo.models"):
                    rec.read([field_name])

    def test_whitelisted_backup_fields_readable(self):
        """Every whitelisted backup field stays readable by a portal user."""
        rec = self.backup_a_prod.with_user(self.user_a)
        model_fields = self.env["k8s.odoo.backup"]._fields
        readable = sorted(PORTAL_VISIBLE_BACKUP_FIELDS & set(model_fields))
        self.assertEqual(
            set(readable),
            PORTAL_VISIBLE_BACKUP_FIELDS,
            "PORTAL_VISIBLE_BACKUP_FIELDS references fields absent from model.",
        )
        values = rec.read(readable)
        self.assertTrue(values)

    def test_drift_guard_non_whitelisted_backup_fields_hidden(self):
        """Deny-by-default: any non-whitelisted backup field is hidden."""
        Backup = self.env["k8s.odoo.backup"]
        rec = self.backup_a_prod.with_user(self.user_a)
        leaked = []
        for field_name in Backup._fields:
            if field_name in PORTAL_VISIBLE_BACKUP_FIELDS:
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
            "Non-whitelisted backup fields readable by a portal user "
            "(add groups= or extend the whitelist): %s" % leaked,
        )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestBackupSelfService(HttpCase):
    """End-to-end portal controller: list/download/backup-now/restore (c-f)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    def _csrf_token(self):
        """Mint a CSRF token valid for the authenticated session."""
        return http.Request.csrf_token(self)

    # -------------------------------------------------------------- (a) list
    def test_backups_list_shows_own_not_other(self):
        """List page for A's prod instance shows its backup, not B's."""
        self.authenticate("backup_user_a", "backup_user_a")
        resp = self.url_open(
            "/my/instances/%d/backups" % self.inst_a_prod.id
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn(self.backup_a_prod.name, body)
        # B's backup name must never appear.
        self.assertNotIn(self.backup_b_prod.name, body)
        # No secret leaks into the page.
        self.assertNotIn("SECRET-TOKEN-A", body)
        self.assertNotIn("presigned-A", body)

    def test_backups_list_non_owned_instance_redirects(self):
        """List page for a non-owned instance redirects, leaks nothing."""
        self.authenticate("backup_user_a", "backup_user_a")
        resp = self.url_open(
            "/my/instances/%d/backups" % self.inst_b_prod.id,
            allow_redirects=False,
        )
        self.assertIn(resp.status_code, (301, 302, 303, 404))
        self.assertNotIn(self.backup_b_prod.name, resp.text)

    # -------------------------------------------------------------- (c) backup-now
    def test_backup_now_owned_creates_record(self):
        """POST backup-now on an owned instance creates a pending backup."""
        self.authenticate("backup_user_a", "backup_user_a")
        Backup = self.env["k8s.odoo.backup"]
        before = Backup.search_count([("instance_id", "=", self.inst_a_prod.id)])
        with patch(_BACKUP_CR) as cr:
            resp = self.url_open(
                "/my/instances/%d/backup" % self.inst_a_prod.id,
                data={"csrf_token": self._csrf_token(), "format": "zip"},
            )
        self.assertEqual(resp.status_code, 200)
        after = Backup.search_count([("instance_id", "=", self.inst_a_prod.id)])
        self.assertEqual(after, before + 1, "A new backup must be created.")
        # The k8s CR hook was invoked (under sudo) -- not skipped.
        self.assertTrue(cr.called)
        new = Backup.search(
            [("instance_id", "=", self.inst_a_prod.id)],
            order="create_date desc",
            limit=1,
        )
        self.assertEqual(new.state, "pending")

    def test_backup_now_non_owned_refused(self):
        """POST backup-now on a non-owned instance creates nothing (IDOR)."""
        self.authenticate("backup_user_a", "backup_user_a")
        Backup = self.env["k8s.odoo.backup"]
        before = Backup.search_count([("instance_id", "=", self.inst_b_prod.id)])
        with patch(_BACKUP_CR) as cr:
            resp = self.url_open(
                "/my/instances/%d/backup" % self.inst_b_prod.id,
                data={"csrf_token": self._csrf_token(), "format": "zip"},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        after = Backup.search_count([("instance_id", "=", self.inst_b_prod.id)])
        self.assertEqual(after, before, "No backup may be created for a foreign instance.")
        self.assertFalse(cr.called, "The k8s CR hook must not run for an IDOR attempt.")

    # -------------------------------------------------------------- (f) audit
    def test_backup_now_posts_audit_message(self):
        """Backup-now posts an audit chatter message on the instance."""
        self.authenticate("backup_user_a", "backup_user_a")
        before = len(self.inst_a_prod.message_ids)
        with patch(_BACKUP_CR):
            self.url_open(
                "/my/instances/%d/backup" % self.inst_a_prod.id,
                data={"csrf_token": self._csrf_token(), "format": "zip"},
            )
        self.inst_a_prod.invalidate_recordset()
        messages = self.inst_a_prod.message_ids
        self.assertGreater(len(messages), before, "An audit message must be posted.")
        latest = messages[0]
        self.assertIn("ackup", latest.body or "")
        self.assertEqual(latest.author_id, self.user_a.partner_id)

    # -------------------------------------------------------------- (d) restore
    def test_restore_staging_owned_creates_restore(self):
        """Restore to an owned staging instance creates a k8s.odoo.restore."""
        self.authenticate("backup_user_a", "backup_user_a")
        Restore = self.env["k8s.odoo.restore"]
        before = Restore.search_count([])
        with patch(_RESTORE_CR) as cr:
            resp = self.url_open(
                "/my/instances/backup/%d/restore" % self.backup_a_staging.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.assertEqual(resp.status_code, 200)
        after = Restore.search_count([])
        self.assertEqual(after, before + 1)
        self.assertTrue(cr.called)
        new = Restore.search([], order="create_date desc", limit=1)
        self.assertEqual(new.target_instance_id, self.inst_a_staging)

    def test_restore_production_refused(self):
        """Restore targeting a production instance is refused (never exposed)."""
        self.authenticate("backup_user_a", "backup_user_a")
        Restore = self.env["k8s.odoo.restore"]
        before = Restore.search_count([])
        with patch(_RESTORE_CR) as cr:
            resp = self.url_open(
                "/my/instances/backup/%d/restore" % self.backup_a_prod.id,
                data={"csrf_token": self._csrf_token()},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        after = Restore.search_count([])
        self.assertEqual(after, before, "Production restore must never create a record.")
        self.assertFalse(cr.called)

    def test_restore_non_owned_backup_refused(self):
        """Restore from a non-owned backup is refused (IDOR)."""
        self.authenticate("backup_user_a", "backup_user_a")
        Restore = self.env["k8s.odoo.restore"]
        before = Restore.search_count([])
        with patch(_RESTORE_CR) as cr:
            resp = self.url_open(
                "/my/instances/backup/%d/restore" % self.backup_b_prod.id,
                data={"csrf_token": self._csrf_token()},
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        after = Restore.search_count([])
        self.assertEqual(after, before)
        self.assertFalse(cr.called)

    def test_restore_staging_posts_audit_message(self):
        """Restore posts an audit chatter message on the target instance."""
        self.authenticate("backup_user_a", "backup_user_a")
        before = len(self.inst_a_staging.message_ids)
        with patch(_RESTORE_CR):
            self.url_open(
                "/my/instances/backup/%d/restore" % self.backup_a_staging.id,
                data={"csrf_token": self._csrf_token()},
            )
        self.inst_a_staging.invalidate_recordset()
        messages = self.inst_a_staging.message_ids
        self.assertGreater(len(messages), before)
        self.assertEqual(messages[0].author_id, self.user_a.partner_id)

    # -------------------------------------------------------------- (e) download
    def test_download_owned_redirects_to_presigned(self):
        """Download of an owned, completed backup redirects to the presign."""
        self.authenticate("backup_user_a", "backup_user_a")
        with patch(_PRESIGN, return_value="https://minio.invalid/presigned-OK") as p:
            resp = self.url_open(
                "/my/instances/backup/%d/download" % self.backup_a_prod.id,
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303))
        self.assertEqual(
            resp.headers.get("Location"),
            "https://minio.invalid/presigned-OK",
        )
        self.assertTrue(p.called, "Presign must be generated under sudo.")

    def test_download_non_owned_refused_no_presign(self):
        """Download of a non-owned backup is refused; no presign generated."""
        self.authenticate("backup_user_a", "backup_user_a")
        with patch(_PRESIGN, return_value="https://leak.invalid/SHOULD-NOT") as p:
            resp = self.url_open(
                "/my/instances/backup/%d/download" % self.backup_b_prod.id,
                allow_redirects=False,
            )
        self.assertIn(resp.status_code, (301, 302, 303, 403, 404))
        self.assertNotIn("SHOULD-NOT", resp.text)
        self.assertFalse(p.called, "No presign for a non-owned backup (IDOR).")
