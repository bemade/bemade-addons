from odoo.tests import TransactionCase


class TestParticipantScopeStub(TransactionCase):
    """Placeholder: kept so a minimal, dependency-free check always
    collects even if the behavioral suite (AC1-AC5) added by the test
    stage below needs adjustment.
    """

    def test_model_fields_registered(self):
        participant_fields = self.env["mail.conversation.participant"]._fields
        self.assertIn("receives_updates", participant_fields)
        self.assertIn("visibility", participant_fields)
        conversation_fields = self.env["mail.conversation"]._fields
        self.assertIn("external_visibility", conversation_fields)


# ------------------------------------------------------------
# Behavioral tests (AC1-AC5) -- scaffolded here, implemented by the
# test stage. Not yet populated: see epic 05 for _notify_get_recipients
# and epic 03 for inbound routing, out of scope for this module.
# ------------------------------------------------------------
