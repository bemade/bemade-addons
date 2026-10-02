// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_triage_tour
 *
 * Drives the triage list the way a user does: row content, then every
 * triage action on a single row, then a bulk action on a subset. Server
 * state is asserted by TestConversationTriageTour. Selectors rely on
 * stable `name=` attributes, not on translated labels, wherever possible.
 */
import {registry} from "@web/core/registry";

const row = (name) => `.o_list_renderer tr.o_data_row:contains('${name}')`;
const rowButton = (name, action) => `${row(name)} button[name='${action}']`;
const gone = (name) => `.o_list_renderer:not(:has(tr.o_data_row:contains('${name}')))`;

function toggleFilter(label) {
  return [
    {
      content: "Open the filter menu",
      trigger: ".o_control_panel .o_searchview_dropdown_toggler",
      run: "click",
    },
    {
      content: `Toggle the '${label}' filter`,
      trigger: `.o_filter_menu .o_menu_item:contains('${label}')`,
      run: "click",
    },
    {
      content: "Close the filter menu",
      trigger: ".o_control_panel .o_searchview_dropdown_toggler",
      run: "click",
    },
  ];
}

registry.category("web_tour.tours").add("conversation_triage_tour", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => [
    {
      content: "The triage list mounts",
      trigger: ".o_conversation_triage_list .o_list_renderer, .o_list_renderer",
    },
    {
      content: "Alpha shows its snippet, its linked record and is unread (bold)",
      trigger: `${row(
        "Alpha"
      )}.fw-bold:contains('Snippet for Alpha'):contains('Tour Linked Co')`,
    },
    // Mark read
    {
      content: "Mark Alpha read",
      trigger: rowButton("Alpha", "action_triage_mark_read"),
      run: "click",
    },
    {
      content: "Alpha is no longer bold but still listed",
      trigger: `${row("Alpha")}:not(.fw-bold)`,
    },
    // Hide / Unhide
    {
      content: "Hide Alpha",
      trigger: rowButton("Alpha", "action_triage_hide"),
      run: "click",
    },
    {trigger: gone("Alpha"), content: "Alpha left my list"},
    ...toggleFilter("Hidden by me"),
    {
      content: "Alpha is found again",
      trigger: rowButton("Alpha", "action_triage_unhide"),
      run: "click",
    },
    ...toggleFilter("Hidden by me"),
    {content: "Alpha is back in my list", trigger: row("Alpha")},
    // Done / Reopen
    {
      content: "Done on Beta",
      trigger: rowButton("Beta", "action_triage_done"),
      run: "click",
    },
    {trigger: gone("Beta"), content: "Beta left the list"},
    ...toggleFilter("Done"),
    {
      content: "Reopen Beta",
      trigger: rowButton("Beta", "action_triage_reopen"),
      run: "click",
    },
    ...toggleFilter("Done"),
    {content: "Beta is open again", trigger: row("Beta")},
    // Snooze
    {
      content: "Snooze Gamma",
      trigger: rowButton("Gamma", "action_triage_open_snooze_wizard"),
      run: "click",
    },
    {
      content: "Apply the default 'Tomorrow' preset",
      trigger: ".modal button[name='action_apply']",
      run: "click",
    },
    {trigger: gone("Gamma"), content: "Gamma left my list"},
    // Assign
    {
      content: "Assign Delta",
      trigger: rowButton("Delta", "action_triage_open_assign_wizard"),
      run: "click",
    },
    {
      content: "Pick the colleague",
      trigger: ".modal div[name='user_id'] input",
      run: "edit Tour Colleague",
    },
    {
      trigger: ".o-autocomplete--dropdown-item:contains('Tour Colleague')",
      run: "click",
    },
    {
      trigger: ".modal button[name='action_apply']",
      run: "click",
    },
    {
      content: "The colleague's name is on Delta's row",
      trigger: `${row("Delta")}:contains('Tour Colleague')`,
    },
    // Bulk on a subset
    {
      content: "Select Epsilon",
      trigger: `${row("Epsilon")} .o_list_record_selector input`,
      run: "click",
    },
    {
      content: "Select Zeta",
      trigger: `${row("Zeta")} .o_list_record_selector input`,
      run: "click",
    },
    {
      content: "Done on the selection",
      trigger: ".o_control_panel button[name='action_triage_done']",
      run: "click",
    },
    {trigger: gone("Epsilon"), content: "Epsilon left"},
    {trigger: gone("Zeta"), content: "Zeta left"},
    {
      content: "Eta stays, unselected",
      trigger: `${row(
        "Eta"
      )}:not(.o_data_row_selected):not(:has(.o_list_record_selector input:checked))`,
    },
    // Open
    {
      content: "Open Eta",
      trigger: `${row("Eta")} td[name='name']`,
      run: "click",
    },
    {
      content: "The form with chatter opens",
      trigger: ".o_form_view .o-mail-Chatter",
    },
  ],
});
