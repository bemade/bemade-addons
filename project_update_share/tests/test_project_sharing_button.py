# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: a collaborator reaches the updates from Project Sharing (tour).

ACCEPTANCE CRITERIA
- A portal collaborator opening the project lands in Project Sharing, whose
  control panel shows an "Updates" button.
- Clicking it opens the project's portal updates page, listing the updates
  shared with that collaborator.
- The button is shown for every project in Project Sharing, whether or not
  anything has been shared yet (the page says when there is nothing).
"""
from odoo import Command
from odoo.tests.common import HttpCase, tagged

from .common import ProjectUpdateShareCommon


@tagged("post_install", "-at_install")
class TestProjectSharingButton(HttpCase, ProjectUpdateShareCommon):
    def test_updates_button_in_project_sharing(self):
        self._update(
            name="For the collaborator",
            internal_only=False,
            recipient_ids=[Command.set(self.collaborator.ids)],
        )
        self.start_tour(
            "/my/projects/%s/project_sharing" % self.project.id,
            "project_update_share_sharing_button",
            login="pus-collaborator",
        )
