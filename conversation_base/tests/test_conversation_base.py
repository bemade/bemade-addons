from odoo.tests.common import TransactionCase


class TestConversationBaseStub(TransactionCase):
    """Placeholder: the real behavioral test suite (AC2-AC9 per
    02-design.md's Test plan) is written in the TEST phase of this task's
    dev cycle. This stub only asserts the module installs and the model
    is registered, so `pytest-odoo`/`--test-tags` runs have something to
    collect during the CODE phase.
    """

    def test_model_registered(self):
        self.assertIn("mail.conversation", self.env)
