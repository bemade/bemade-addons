// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// The server cost of opening the window is guarded by
// TestReplyWizardAttachmentAccess (tests/test_reply_wizard_attachment_access.py).
import {registry} from "@web/core/registry";
import steps from "./reply_window.steps";
import {toTourStep} from "./to_tour_step";

registry.category("web_tour.tours").add("conversation_inbox_reply_window_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
