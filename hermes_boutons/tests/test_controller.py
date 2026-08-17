# Copyright 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, http
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install", "hermes_boutons")
class TestHermesBoutonsController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="hermes_approver",
            groups="base.group_user",
        )
        cls.other_user = new_test_user(
            cls.env,
            login="hermes_other_user",
            groups="base.group_user",
        )
        cls.channel = cls.env["discuss.channel"].sudo().create(
            {
                "name": "Hermes approval test",
                "channel_type": "channel",
                "channel_member_ids": [
                    Command.create({"partner_id": cls.user.partner_id.id})
                ],
            }
        )
        cls.private_channel = cls.env["discuss.channel"].sudo().create(
            {
                "name": "Hermes inaccessible approval test",
                "channel_type": "group",
                "channel_member_ids": [
                    Command.create({"partner_id": cls.other_user.partner_id.id})
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.authenticate(self.user.login, "unused")

    def _message_count(self):
        return self.env["mail.message"].sudo().search_count(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.channel.id),
                ("body", "ilike", "/approve"),
            ]
        )

    def test_get_does_not_approve(self):
        before = self._message_count()

        response = self.url_open(
            "/hermes/repondre",
            params={"canal": self.channel.id, "cmd": "/approve"},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self._message_count(), before)

    def test_post_without_csrf_is_rejected(self):
        before = self._message_count()

        response = self.url_open(
            "/hermes/repondre",
            data={"canal": self.channel.id, "cmd": "/approve"},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._message_count(), before)

    def test_post_with_csrf_approves_as_authenticated_user(self):
        before = self._message_count()

        response = self.url_open(
            "/hermes/repondre",
            data={
                "canal": self.channel.id,
                "cmd": "/approve",
                "csrf_token": http.Request.csrf_token(self),
            },
            headers={"X-Hermes-Ajax": "1"},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self._message_count(), before + 1)
        message = self.env["mail.message"].sudo().search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.channel.id),
                ("body", "ilike", "/approve"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertEqual(message.author_id, self.user.partner_id)

    def test_post_to_inaccessible_channel_is_rejected(self):
        before = self.env["mail.message"].sudo().search_count(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.private_channel.id),
            ]
        )

        response = self.url_open(
            "/hermes/repondre",
            data={
                "canal": self.private_channel.id,
                "cmd": "/approve",
                "csrf_token": http.Request.csrf_token(self),
            },
            headers={"X-Hermes-Ajax": "1"},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.env["mail.message"].sudo().search_count(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", self.private_channel.id),
                ]
            ),
            before,
        )
