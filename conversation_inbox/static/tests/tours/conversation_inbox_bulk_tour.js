// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_inbox_bulk_tour
 *
 * Bulk actions in the inbox viewer act on exactly the ticked rows, never
 * fetch a message body, ask for ONE confirmation before a bulk delete, and
 * report a partial failure without losing the rows that failed.
 *
 * The mailbox is the stub seeded by TestConversationInboxBulkTour in
 * tests/test_conversation_inbox_bulk_tour.py (four messages on one page;
 * moving message "4" to the Trash always fails).
 */
import {registry} from "@web/core/registry";

const row = (subject) => `.o_inbox_row:has(.card-header:contains('${subject}'))`;

registry.category("web_tour.tours").add("conversation_inbox_bulk_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => [
    {
      content: "The inbox client action mounts",
      trigger: ".o_conversation_inbox",
    },
    {
      content: "Use the tour's own account",
      trigger: ".o_conversation_inbox",
      run() {
        const select = document.querySelector("#o_conversation_inbox_transport");
        const option =
          select &&
          [...select.options].find((opt) => opt.textContent.trim() === "Bulk Mailbox");
        if (option && !option.selected) {
          select.value = option.value;
          select.dispatchEvent(new Event("change", {bubbles: true}));
        }
      },
    },
    {
      content: "The four messages are listed",
      trigger: `.o_conversation_inbox_list ${row("Bulk Message D")}`,
    },
    {
      content: "Nothing is ticked, so there is no bulk bar",
      trigger: ".o_conversation_inbox:not(:has(.o_inbox_bulk_bar))",
    },
    {
      content: "Tick message A",
      trigger: `${row("Bulk Message A")} input.o_inbox_select`,
      run: "check",
    },
    {
      content: "Tick message C",
      trigger: `${row("Bulk Message C")} input.o_inbox_select`,
      run: "check",
    },
    {
      content: "The bulk bar counts the two ticked rows",
      trigger: ".o_inbox_bulk_bar .o_inbox_selected_count:contains('2')",
    },
    {
      content: "Clicking a checkbox did not open the row",
      trigger: ".o_conversation_inbox:not(:has(.card-body))",
    },
    {
      content: "Archive the selection",
      trigger: ".o_inbox_bulk_bar .o_inbox_bulk_archive",
      run: "click",
    },
    {
      content: "Only A and C left the list; B and D remain",
      trigger: `.o_conversation_inbox_list:not(:has(.card-header:contains('Bulk Message A'))):not(:has(.card-header:contains('Bulk Message C'))):has(.card-header:contains('Bulk Message B')):has(.card-header:contains('Bulk Message D'))`,
    },
    {
      content: "The selection left with the rows",
      trigger: ".o_conversation_inbox:not(:has(.o_inbox_bulk_bar))",
    },
    {
      content: "Select every row of the page",
      trigger: ".o_inbox_select_all",
      run: "check",
    },
    {
      content: "Both remaining rows are ticked",
      trigger: ".o_inbox_selected_count:contains('2')",
    },
    {
      content: "Delete the selection",
      trigger: ".o_inbox_bulk_bar .o_inbox_bulk_delete",
      run: "click",
    },
    {
      content: "One confirmation states how many messages go to the Trash",
      trigger: ".modal:contains('2 messages') footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "Cancelling left both rows in place",
      trigger:
        ".o_conversation_inbox:not(:has(.modal)) .o_conversation_inbox_list:has(.card-header:contains('Bulk Message B')):has(.card-header:contains('Bulk Message D'))",
    },
    {
      content: "Delete the selection again",
      trigger: ".o_inbox_bulk_bar .o_inbox_bulk_delete",
      run: "click",
    },
    {
      content: "Confirm",
      trigger: ".modal:contains('2 messages') footer button:contains('Delete')",
      run: "click",
    },
    {
      content: "The failure is reported with the server's own message and the count",
      trigger:
        ".o_notification:contains('1 of 2 messages failed'):contains('Trash refused for message 4')",
    },
    {
      content: "The message that went through is gone; the failed one stays, ticked",
      trigger: `.o_conversation_inbox_list:not(:has(.card-header:contains('Bulk Message B'))) ${row(
        "Bulk Message D"
      )} input.o_inbox_select:checked`,
    },
    {
      content: "The bulk bar now counts the one failed row",
      trigger: ".o_inbox_selected_count:contains('1')",
    },
    {
      content: "Mark the failed row's selection as read instead",
      trigger: ".o_inbox_bulk_bar .o_inbox_bulk_mark_read",
      run: "click",
    },
    {
      content: "Marked as read, and the row stays listed",
      trigger: `.o_notification:contains('Marked as read'), .o_conversation_inbox_list ${row(
        "Bulk Message D"
      )}`,
    },
    {
      content: "Message D is still listed after Mark read",
      trigger: `.o_conversation_inbox_list ${row("Bulk Message D")}`,
    },
  ],
});
