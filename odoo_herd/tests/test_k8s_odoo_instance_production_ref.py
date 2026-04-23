from typing import Any, cast

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger


class TestOdooInstanceProductionRef(TransactionCase):
    @classmethod
    def setUpClass(cls):  # type: ignore[misc]
        super().setUpClass()
        env: Any = cls.env
        cls.cluster = cast(
            Any,
            env["k8s.cluster"].create(
                {
                    "name": "test-cluster",
                    "api_endpoint": "https://k8s.example.com",
                    "kubeconfig": "{}",
                    "default_namespace": "odoo",
                    "webhook_base_url": "http://odoo.example.com",
                }
            ),
        )

    def _make_instance(self, **kwargs):
        vals = {
            "cluster_id": self.cluster.id,
            "name": "prod",
            "namespace": "odoo",
            "environment": "production",
        }
        vals.update(kwargs)
        env: Any = self.env
        return cast(Any, env["k8s.odoo.instance"].create(vals))

    @mute_logger("odoo.sql_db")
    def test_production_with_source_ref_raises(self):
        prod = self._make_instance(name="prod-a", environment="production")
        with self.assertRaises(UserError):
            self._make_instance(
                name="prod-b",
                environment="production",
                production_instance_id=prod.id,
            )

    def test_staging_with_source_ref_saves_cleanly(self):
        prod = self._make_instance(name="prod-c", environment="production")
        staging = self._make_instance(
            name="stg-c",
            environment="staging",
            production_instance_id=prod.id,
        )
        self.assertEqual(staging.environment, "staging")
        self.assertEqual(staging.production_instance_id, prod)
