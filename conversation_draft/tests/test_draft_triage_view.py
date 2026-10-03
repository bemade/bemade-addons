# Acceptance criteria (conversation triage list, draft indicator):
#   * With conversation_draft installed, the triage list view still builds
#     and carries the draft fields.
#   * A conversation with a pending draft reads back as having one, and
#     names the user working on it.

from .common import DraftCommon


class TestDraftTriageView(DraftCommon):
    def test_triage_view_with_draft_builds(self):
        view = self.env.ref("conversation_base.mail_conversation_view_list_triage")
        views = (
            self.env["mail.conversation"]
            .with_user(self.user_a)
            .get_views([(view.id, "list")])
        )
        arch = views["views"]["list"]["arch"]
        self.assertIn("has_pending_draft", arch)
        self.assertIn("draft_editor_id", arch)

        draft = self._open_draft(self.user_a)
        row = (
            self.conversation.with_user(self.user_a)
            .search_read(
                [("id", "=", self.conversation.id)],
                ["has_pending_draft", "draft_editor_id"],
            )[0]
        )
        self.assertTrue(draft)
        self.assertTrue(row["has_pending_draft"])
        self.assertEqual(row["draft_editor_id"][0], self.user_a.id)
