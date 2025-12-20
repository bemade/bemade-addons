from typing import Any

from lxml import etree as ET
from odoo.tests import TransactionCase, Form


class TestCreateInstanceWizardView(TransactionCase):
    @classmethod
    def setUpClass(cls):  # type: ignore[misc]
        super().setUpClass()
        cls.view = cls.env.ref("odoo_herd.view_k8s_create_instance_wizard_form")
        cls.fields_def = cls.env["k8s.create.instance.wizard"].fields_get()
        cls.form_fields = cls._extract_form_fields(cls.view.arch_db)
        cls.cluster = cls.env["k8s.cluster"].create(
            {
                "name": "test-cluster",
                "api_endpoint": "https://k8s.example.com",
                "kubeconfig": "{}",
                "default_namespace": "odoo",
                "webhook_base_url": "http://odoo.example.com",
            }
        )

    def _make_wizard(self, **kwargs):
        vals = {
            "cluster_id": self.cluster.id,
            "name": "demo",
            "namespace": "odoo",
            "image": "odoo:18.0",
            "replicas": 1,
            "admin_password": "admin",
            "ingress_hosts": "odoo.example.com",
            "filestore_size": "10Gi",
            "filestore_storage_class": "standard",
            "cluster_issuer": "lets-encrypt",
        }
        vals.update(kwargs)
        return self.env["k8s.create.instance.wizard"].create(vals)

    @staticmethod
    def _extract_form_fields(arch: str) -> dict[str, Any]:
        """Return mapping of field name -> etree element attributes from form arch."""
        tree = ET.fromstring(arch.encode())  # type: ignore[attr-defined]
        fields: dict[str, Any] = {}
        for field in tree.xpath("//field"):
            name = field.get("name")
            if not name:
                continue
            fields[name] = field.attrib
        return fields

    def test_all_required_fields_are_present(self):
        missing = []
        for name, definition in self.fields_def.items():
            if definition.get("required"):
                if name not in self.form_fields:
                    missing.append(name)
        self.assertFalse(
            missing, msg=f"Required fields missing from form view: {missing}"
        )

    def test_critical_fields_not_readonly(self):
        critical = [
            "cluster_id",
            "name",
            "namespace",
            "image",
            "admin_password",
            "ingress_hosts",
            "initialization_mode",
            "filestore_size",
            "filestore_storage_class",
            "cluster_issuer",
            "replicas",
            "image_pull_secret",
        ]
        readonly = [
            f
            for f in critical
            if self.form_fields.get(f, {}).get("readonly") not in (None, False)
        ]
        self.assertFalse(
            readonly, msg=f"Critical fields unexpectedly readonly in view: {readonly}"
        )

    def test_restore_and_backup_fields_present_with_visibility_guards(self):
        restore_fields = ["restore_url", "restore_database", "restore_master_password"]
        backup_fields = ["backup_id"]

        for name in restore_fields + backup_fields:
            self.assertIn(name, self.form_fields)

        # Visibility/required expressions should reference initialization_mode
        restore_required = self.form_fields["restore_url"].get("required", "")
        self.assertIn("initialization_mode", restore_required)

        backup_required = self.form_fields["backup_id"].get("required", "")
        self.assertIn("initialization_mode", backup_required)

    def test_fresh_fields_writable_via_form(self):
        wiz = self._make_wizard(initialization_mode="fresh")
        with Form(wiz) as f:
            f.name = "demo2"
            f.namespace = "odoo2"
            f.image = "odoo:custom"
            f.admin_password = "pw"
            f.ingress_hosts = "demo2.example.com"
            f.replicas = 2
            f.cluster_issuer = "issuer"
            f.filestore_size = "5Gi"
            f.filestore_storage_class = "fast"
            f.image_pull_secret = "regcred"
        self.assertEqual(wiz.name, "demo2")
        self.assertEqual(wiz.ingress_hosts, "demo2.example.com")

    def test_restore_fields_visible_and_writable_via_form(self):
        wiz = self._make_wizard(initialization_mode="restore")
        with Form(wiz) as f:
            f.initialization_mode = "restore"
            f.restore_url = "https://source.example.com"
            f.restore_database = "sourcedb"
            f.restore_master_password = "masterpw"
            f.restore_with_filestore = True
            f.restore_neutralize = False
        self.assertEqual(wiz.restore_url, "https://source.example.com")
        self.assertEqual(wiz.restore_database, "sourcedb")
        self.assertTrue(wiz.restore_with_filestore)
        self.assertFalse(wiz.restore_neutralize)
