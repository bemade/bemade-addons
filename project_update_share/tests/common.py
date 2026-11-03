# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo.tests.common import TransactionCase, new_test_user


class ProjectUpdateShareCommon(TransactionCase):
    """A portal-visible project with one portal follower, one portal
    collaborator, one internal follower and one portal outsider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.customer = cls.env["res.partner"].create({
            "name": "Customer Co", "is_company": True,
        })
        cls.manager = new_test_user(
            cls.env, login="pus-manager", groups="project.group_project_manager",
        )
        cls.follower_user = new_test_user(
            cls.env, login="pus-follower", groups="base.group_portal",
        )
        cls.collaborator_user = new_test_user(
            cls.env, login="pus-collaborator", groups="base.group_portal",
        )
        cls.outsider_user = new_test_user(
            cls.env, login="pus-outsider", groups="base.group_portal",
        )
        cls.colleague = new_test_user(
            cls.env, login="pus-colleague", groups="project.group_project_user",
        )
        cls.follower = cls.follower_user.partner_id
        cls.collaborator = cls.collaborator_user.partner_id
        cls.outsider = cls.outsider_user.partner_id
        cls.project = cls.env["project.project"].create({
            "name": "Shared Project",
            "partner_id": cls.customer.id,
            "privacy_visibility": "portal",
        })
        cls.project.message_subscribe(
            partner_ids=(cls.follower | cls.colleague.partner_id).ids,
        )
        # As the project's Share wizard does: a collaborator also follows.
        cls.env["project.collaborator"].create({
            "project_id": cls.project.id, "partner_id": cls.collaborator.id,
        })
        cls.project.message_subscribe(partner_ids=cls.collaborator.ids)
        cls.Update = cls.env["project.update"].with_user(cls.manager)
        cls.mt_comment = cls.env.ref("mail.mt_comment")

    def _update(self, **vals):
        return self.Update.create({
            "name": "Week 45",
            "status": "on_track",
            "project_id": self.project.id,
            "description": "<p>Invoices now show tracking.</p>",
            **vals,
        })

    @staticmethod
    def _shares(update):
        """The share messages posted on ``update``, oldest first."""
        return update.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ).sorted("id")
