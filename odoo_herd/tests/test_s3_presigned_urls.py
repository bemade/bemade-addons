"""Presigned S3 URLs must be signed for an endpoint the user's browser can reach.

Use case: the S3 config's ``endpoint`` is an in-cluster address (e.g. a
``*.svc.cluster.local`` service) used by the operator and by Odoo's own
server-side calls. SigV4 signs the Host header, so a presigned URL cannot be
rewritten to a public host after signing: it has to be minted for the public
host from the start.

Acceptance criteria:
- With ``public_endpoint`` set, the backup download URL and the upload wizard's
  PUT URL use the public host, path-style (``<public>/<bucket>/<key>``).
- With ``public_endpoint`` empty, both fall back to ``endpoint`` (unchanged
  behaviour for configs whose endpoint is already public).
- Server-side calls are unaffected: ``endpoint`` stays the internal address.
"""

import base64
from contextlib import contextmanager
from typing import Any, cast
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestS3PresignedUrls(TransactionCase):
    @classmethod
    @mute_logger("odoo.addons.odoo_herd.models.k8s_cluster")  # no cluster to reach
    def setUpClass(cls):  # type: ignore[misc]
        super().setUpClass()
        env: Any = cls.env
        cls.s3_config = cast(
            Any,
            env["k8s.s3.config"].create(
                {
                    "name": "rgw",
                    "endpoint": "http://rgw-s3.storage.svc.cluster.local:7480/",
                    "public_endpoint": "https://s3.example.com/",
                    "bucket": "odoo-backups",
                    "credentials_secret_name": "backup-creds",
                }
            ),
        )
        cls.cluster = cast(
            Any,
            env["k8s.cluster"].create(
                {
                    "name": "test-cluster",
                    "api_endpoint": "https://k8s.example.com",
                    "kubeconfig": "{}",
                    "default_namespace": "odoo",
                    "webhook_base_url": "http://odoo.example.com",
                    "backup_s3_config_id": cls.s3_config.id,
                }
            ),
        )
        cls.instance = cast(
            Any,
            env["k8s.odoo.instance"].create(
                {
                    "cluster_id": cls.cluster.id,
                    "name": "acme",
                    "namespace": "odoo",
                    "environment": "production",
                }
            ),
        )
        # state=completed skips creating the OdooBackupJob CR in Kubernetes
        cls.backup = cast(
            Any,
            env["k8s.odoo.backup"].create(
                {
                    "instance_id": cls.instance.id,
                    "state": "completed",
                    "bucket": "odoo-backups",
                    "object_key": "acme/20261002-095430.zip",
                }
            ),
        )

    def setUp(self):
        self.enterContext(mute_logger("odoo.addons.odoo_herd.models.k8s_cluster"))
        super().setUp()

    @contextmanager
    def _mock_credentials(self):
        secret = MagicMock()
        secret.data = {
            "accessKey": base64.b64encode(b"AKIDEXAMPLE").decode(),
            "secretKey": base64.b64encode(b"secret").decode(),
        }
        core_api = MagicMock()
        core_api.read_namespaced_secret.return_value = secret
        with (
            patch.object(
                type(self.env["k8s.cluster"]), "_get_k8s_client", return_value=None
            ),
            patch("kubernetes.client.CoreV1Api", return_value=core_api),
        ):
            yield

    def _upload_url(self):
        wizard = cast(
            Any,
            self.env["k8s.upload.backup.wizard"].create(
                {
                    "cluster_id": self.cluster.id,
                    "backup_name": "acme",
                }
            ),
        )
        with self._mock_credentials():
            wizard.action_generate_upload_url()
        return wizard.upload_url, wizard.object_key

    def test_download_url_signed_for_public_endpoint(self):
        with self._mock_credentials():
            url = urlsplit(self.backup._generate_presigned_url())
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.netloc, "s3.example.com")
        self.assertEqual(url.path, "/odoo-backups/acme/20261002-095430.zip")
        self.assertIn("X-Amz-Signature=", url.query)

    def test_upload_url_signed_for_public_endpoint(self):
        upload_url, object_key = self._upload_url()
        url = urlsplit(upload_url)
        self.assertEqual(url.netloc, "s3.example.com")
        self.assertEqual(url.path, f"/odoo-backups/{object_key}")
        self.assertIn("X-Amz-Signature=", url.query)

    def test_falls_back_to_endpoint_without_public_endpoint(self):
        self.s3_config.public_endpoint = False
        with self._mock_credentials():
            download = urlsplit(self.backup._generate_presigned_url())
        upload = urlsplit(self._upload_url()[0])
        for url in (download, upload):
            self.assertEqual(url.netloc, "rgw-s3.storage.svc.cluster.local:7480")
            self.assertTrue(url.path.startswith("/odoo-backups/"))
