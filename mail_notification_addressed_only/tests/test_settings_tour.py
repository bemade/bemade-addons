from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSettingsTour(HttpCase):
    def test_settings_tour(self):
        Rule = self.env["mail.addressed.only.rule"].with_context(active_test=False)
        Rule.search([]).unlink()
        self.start_tour(
            "/odoo/action-base_setup.action_general_configuration",
            "mail_notification_addressed_only_settings",
            login="admin",
        )
        rule = Rule.search([("model", "=", "res.partner")])
        self.assertTrue(rule.active, "The tour must have listed Contact")
