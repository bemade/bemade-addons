// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports. Regression flow (no demo video): a user who is
// neither assignee nor on the team opens a conversation by its direct
// link. Server state (their member row created and read) is asserted by
// TestConversationOpenMarksRead.test_outsider_open_by_url_enrols_reader.
export default [
  {
    id: "form-opens",
    title: "Ouvrir la conversation par son lien",
    narration: "La conversation s'ouvre directement depuis son lien.",
    selector: ".o_form_view .o_control_panel .o_last_breadcrumb_item.active",
    containsText: "Omega",
    action: "assert",
  },
  {
    id: "back-to-list",
    title: "Revenir à la liste",
    narration: "Retournons à la liste des conversations.",
    selector: ".o_control_panel .breadcrumb-item:not(.active) a",
    action: "click",
  },
  {
    id: "list-shown",
    title: "Voir la liste des conversations",
    narration: "La liste des conversations est affichée.",
    selector: ".o_list_view .o_list_renderer",
    action: "assert",
  },
];
