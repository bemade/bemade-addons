"""Unit tests for the ETL Framework core components.

These tests verify core functionality that doesn't require registered models:
- Multiprocessing configuration
- ETL phase enum
- ETLContext creation

For integration tests with real pipelines, see the test_etl_framework module.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.etl_framework import (
    ETLContext,
    ETLPhase,
    MultiprocessingConfig,
)


@tagged("post_install", "-at_install")
class TestMultiprocessingConfig(TransactionCase):
    """Test MultiprocessingConfig behavior."""

    def test_should_use_multiprocessing_enabled(self):
        """Test multiprocessing threshold logic when enabled."""
        config = MultiprocessingConfig(enabled=True, threshold=100)

        self.assertFalse(config.should_use_multiprocessing(50))
        self.assertFalse(config.should_use_multiprocessing(99))
        self.assertTrue(config.should_use_multiprocessing(100))
        self.assertTrue(config.should_use_multiprocessing(1000))

    def test_should_use_multiprocessing_disabled(self):
        """Test multiprocessing is never used when disabled."""
        config = MultiprocessingConfig(enabled=False, threshold=100)

        self.assertFalse(config.should_use_multiprocessing(50))
        self.assertFalse(config.should_use_multiprocessing(100))
        self.assertFalse(config.should_use_multiprocessing(10000))

    def test_get_workers_default(self):
        """Test default worker count is CPU count - 1."""
        import os

        config = MultiprocessingConfig()
        cpu_count = os.cpu_count() or 1
        expected = max(1, cpu_count - 1)
        self.assertEqual(config.get_workers(), expected)

    def test_get_workers_explicit(self):
        """Test explicit worker count is respected."""
        config = MultiprocessingConfig(max_workers=4)
        self.assertEqual(config.get_workers(), 4)


@tagged("post_install", "-at_install")
class TestETLPhase(TransactionCase):
    """Test ETLPhase enum."""

    def test_phase_values(self):
        """Test all expected phases exist."""
        self.assertEqual(ETLPhase.EXTRACT.value, "extract")
        self.assertEqual(ETLPhase.TRANSFORM.value, "transform")
        self.assertEqual(ETLPhase.LOAD.value, "load")


@tagged("post_install", "-at_install")
class TestETLContext(TransactionCase):
    """Test ETLContext dataclass."""

    def test_context_creation(self):
        """Test ETLContext can be created."""
        ctx = ETLContext(cr=None, env=self.env)
        self.assertIsNone(ctx.cr)
        self.assertEqual(ctx.env, self.env)

    def test_context_env_access(self):
        """Test ETLContext env can access models."""
        ctx = ETLContext(cr=None, env=self.env)
        partners = ctx.env["res.partner"].search([], limit=1)
        self.assertIsNotNone(partners)
