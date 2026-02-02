import json
import pytest
from unittest.mock import Mock, patch

from odoo.tests.common import TransactionCase


class TestDeploymentStrategy(TransactionCase):
    """Test deployment strategy functionality in odoo_herd"""

    def setUp(self):
        super().setUp()
        # Create test cluster
        self.cluster = self.env["k8s.cluster"].create(
            {
                "name": "test-cluster",
                "kubeconfig": "fake-config",
                "active": True,
            }
        )

        # Create test instance
        self.instance = self.env["k8s.odoo.instance"].create(
            {
                "name": "test-instance",
                "cluster_id": self.cluster.id,
                "namespace": "default",
                "spec": json.dumps(
                    {
                        "image": "odoo:18.0",
                        "replicas": 1,
                    }
                ),
                "status": json.dumps({"phase": "Running"}),
            }
        )

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_deployment_strategy_recreate_patch(self, mock_k8s_client, mock_custom_api):
        """Test patch data generation for Recreate strategy"""
        self.instance.deployment_strategy_type = "Recreate"

        patch_data = self.instance._build_patch_data()

        expected_strategy = {"type": "Recreate"}
        assert patch_data is not None
        assert patch_data["spec"]["strategy"] == expected_strategy

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_deployment_strategy_rolling_update_patch(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test patch data generation for RollingUpdate strategy"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        self.instance.rolling_update_max_unavailable = "1"
        self.instance.rolling_update_max_surge = "2"

        patch_data = self.instance._build_patch_data()

        expected_strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxUnavailable": "1", "maxSurge": "2"},
        }
        assert patch_data is not None
        assert patch_data["spec"]["strategy"] == expected_strategy

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_deployment_strategy_rolling_update_partial_params(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test RollingUpdate with only maxUnavailable specified"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        self.instance.rolling_update_max_unavailable = "0"
        # rolling_update_max_surge left empty (default)

        patch_data = self.instance._build_patch_data()

        expected_strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxUnavailable": "0"},
        }
        assert patch_data is not None
        assert patch_data["spec"]["strategy"] == expected_strategy

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_deployment_strategy_rolling_update_empty_params(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test RollingUpdate with no rolling update params specified"""
        self.instance.deployment_strategy_type = "RollingUpdate"
        # Both rolling update params left empty

        patch_data = self.instance._build_patch_data()

        expected_strategy = {"type": "RollingUpdate"}
        assert patch_data is not None
        assert patch_data["spec"]["strategy"] == expected_strategy

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_compute_current_deployment_strategy_recreate(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test computing current deployment strategy from cluster (Recreate)"""
        # Mock cluster response
        mock_custom_api.return_value.get_namespaced_custom_object.return_value = {
            "spec": {"strategy": {"type": "Recreate"}}
        }
        mock_k8s_client.return_value = Mock()

        self.cluster._get_k8s_client = Mock(return_value=mock_k8s_client.return_value)

        # Trigger compute
        self.instance._compute_current_values()

        assert self.instance.current_deployment_strategy == "Recreate"

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_compute_current_deployment_strategy_rolling_update(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test computing current deployment strategy from cluster (RollingUpdate)"""
        # Mock cluster response
        mock_custom_api.return_value.get_namespaced_custom_object.return_value = {
            "spec": {
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxUnavailable": "10%", "maxSurge": "20%"},
                }
            }
        }
        mock_k8s_client.return_value = Mock()

        self.cluster._get_k8s_client = Mock(return_value=mock_k8s_client.return_value)

        # Trigger compute
        self.instance._compute_current_values()

        assert self.instance.current_deployment_strategy == "RollingUpdate"

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_compute_current_deployment_strategy_default(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test computing current deployment strategy when no strategy specified"""
        # Mock cluster response with no strategy
        mock_custom_api.return_value.get_namespaced_custom_object.return_value = {
            "spec": {
                "image": "odoo:18.0",
                "replicas": 1,
                # No strategy field
            }
        }
        mock_k8s_client.return_value = Mock()

        self.cluster._get_k8s_client = Mock(return_value=mock_k8s_client.return_value)

        # Trigger compute
        self.instance._compute_current_values()

        # Should default to "Recreate"
        assert self.instance.current_deployment_strategy == "Recreate"

    @patch("k8s_odoo_instance.client.CustomObjectsApi")
    @patch("k8s_odoo_instance.client")
    def test_compute_current_deployment_strategy_cluster_error(
        self, mock_k8s_client, mock_custom_api
    ):
        """Test computing current deployment strategy when cluster is unavailable"""
        # Mock cluster error
        mock_custom_api.return_value.get_namespaced_custom_object.side_effect = (
            Exception("Cluster unavailable")
        )
        mock_k8s_client.return_value = Mock()

        self.cluster._get_k8s_client = Mock(return_value=mock_k8s_client.return_value)

        # Trigger compute
        self.instance._compute_current_values()

        # Should default to "Recreate" when error occurs
        assert self.instance.current_deployment_strategy == "Recreate"

    def test_deployment_strategy_field_values(self):
        """Test deployment strategy field has correct selection values"""
        field = self.instance._fields["deployment_strategy_type"]
        expected_values = [("Recreate", "Recreate"), ("RollingUpdate", "RollingUpdate")]
        assert field.selection == expected_values

    def test_current_deployment_strategy_field_values(self):
        """Test current deployment strategy field has correct selection values"""
        field = self.instance._fields["current_deployment_strategy"]
        expected_values = [("Recreate", "Recreate"), ("RollingUpdate", "RollingUpdate")]
        assert field.selection == expected_values
