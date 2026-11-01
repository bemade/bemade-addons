// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_inbox_tour
 *
 * The regression guard the GTD inbox went without (task #3965).
 *
 * Two autonomous build cycles shipped this feature with the viewer
 * unusable, and the Python suite passed both times, because the failures
 * were not reachable from Python at all: the triage buttons were dead
 * (an inline `doAction` dict carried `view_mode` where the client action
 * schema wants `views`, so every dialog silently failed to open), and the
 * composer's dialog only rendered fields the wizard model happened to
 * expose. Nothing short of clicking the real UI can see either.
 *
 * So the steps below deliberately favour *wiring* over presentation:
 *
 *  - the client action mounts and browse_page's rows reach the DOM;
 *  - every row shows its action icons while collapsed, and the actions
 *    run from there without the message being fetched (the Python side
 *    asserts which envelopes were fetched);
 *  - expanding a row round-trips fetch_envelope and renders the body as
 *    HTML (a real paragraph, not its escaped source);
 *  - Next/Previous actually page (the sequence-window paging behind them
 *    is what made a real mailbox usable);
 *  - each triage button opens its dialog -- the dead-button class of bug;
 *  - the composer opens PREFILLED (subject and quoted original), which is
 *    the part that only exists if default_get ran against the transport;
 *  - the attachments widget sits in the dialog footer, not below the body
 *    editor where it falls under the fold on any real message.
 *
 * Server data and the IMAP stubs are seeded by TestConversationInboxTour
 * in tests/test_conversation_inbox_tour.py -- the transport never touches
 * a socket, so the subjects and body text asserted here come from that
 * fixture.
 */
import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("conversation_inbox_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => [
    {
      content: "The inbox client action mounts",
      trigger: ".o_conversation_inbox",
    },
    {
      // The viewer opens on the first browsable account; another module
      // may have created one in the same database. Switch only if needed,
      // so the usual case does not reload the page under the next steps.
      content: "Use the tour's own account",
      trigger: ".o_conversation_inbox",
      run() {
        const select = document.querySelector("#o_conversation_inbox_transport");
        const option =
          select &&
          [...select.options].find((opt) => opt.textContent.trim() === "Tour Mailbox");
        if (option && !option.selected) {
          select.value = option.value;
          select.dispatchEvent(new Event("change", {bubbles: true}));
        }
      },
    },
    {
      content: "browse_page's first page reached the DOM",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message A')",
    },
    // --------------------------------------------------------------
    // Paging: the Next/Previous wiring over sequence-window paging.
    // --------------------------------------------------------------
    {
      content: "Page forward",
      trigger: ".o_conversation_inbox button:contains('Next'):not(:disabled)",
      run: "click",
    },
    {
      content: "Page 2 shows its own item",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message C')",
    },
    {
      content: "Page back",
      trigger: ".o_conversation_inbox button:contains('Previous'):not(:disabled)",
      run: "click",
    },
    {
      content: "Page 1 is back",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message A')",
    },
    {
      // Tour Message B has no Date: its row shows an empty date, never "false".
      content: "A dateless message is listed without the text 'false'",
      trigger: `.o_inbox_row:has(.card-header:contains('Tour Message B')):not(:contains('false'))`,
    },
    // --------------------------------------------------------------
    // Row actions are on the collapsed row: no message was opened, so no
    // envelope was fetched for any of them (asserted server-side).
    // --------------------------------------------------------------
    {
      content: "A collapsed row already shows its action icons, tooltips included",
      trigger: `.o_inbox_row:has(.card-header:contains('Tour Message A')):not(:has(.card-body)) .o_inbox_row_actions:has(
        button.o_inbox_new_conversation[title][aria-label],
        button.o_inbox_add_existing[title][aria-label],
        button.o_inbox_link_record[title][aria-label],
        button.o_inbox_reassign[title][aria-label],
        button.o_inbox_reply[title][aria-label],
        button.o_inbox_reply_all[title][aria-label],
        button.o_inbox_forward[title][aria-label],
        button.o_inbox_route_alias[title][aria-label],
        button.o_inbox_mark_read[title][aria-label],
        button.o_inbox_archive[title][aria-label],
        button.o_inbox_delete[title][aria-label],
        button.o_inbox_hide[title][aria-label]
      )`,
    },
    // --------------------------------------------------------------
    // The dead-button regression: every triage action must open its
    // dialog, now straight from the collapsed row.
    // --------------------------------------------------------------
    {
      content: "Capture opens the capture wizard from the collapsed row",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message A')) .o_inbox_new_conversation",
      run: "click",
    },
    {
      content: "The capture dialog is up",
      trigger: ".modal footer button:contains('Capture')",
    },
    {
      content: "Dismiss the capture dialog",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "The row stayed collapsed",
      trigger: ".o_conversation_inbox:not(:has(.modal)):not(:has(.card-body))",
    },
    {
      content: "Reassign opens its wizard",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message A')) .o_inbox_reassign",
      run: "click",
    },
    {
      content: "The reassign dialog is up",
      trigger: ".modal footer button:contains('Reassign')",
    },
    {
      content: "Dismiss the reassign dialog",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    // --------------------------------------------------------------
    // The composer: opens, and opens PREFILLED.
    // --------------------------------------------------------------
    {
      content: "Reply opens the composer from the collapsed row",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message A')) .o_inbox_reply",
      run: "click",
    },
    {
      content: "The composer dialog is up",
      trigger: ".modal .o_form_view .o_field_widget[name='body']",
    },
    {
      content: "Subject came back prefixed, not empty",
      trigger:
        ".modal .o_field_widget[name='subject'] input:value(/^Re: Tour Message A$/)",
    },
    {
      content: "The recipient was taken from the original's sender",
      trigger:
        ".modal .o_field_widget[name='to_emails'] input:value(/tourist@example.com/)",
    },
    {
      content: "The original is quoted into the editable body",
      trigger:
        ".modal .o_field_widget[name='body']:contains('the quote you asked for')",
    },
    {
      // The UX fix: below the body editor this control sits under
      // the fold on a message of ordinary length, so attaching a
      // file means scrolling past the whole draft first.
      content: "The attachments control is in the footer, not under the body",
      trigger: ".modal footer .o_field_widget[name='attachment_ids']",
    },
    {
      // Same reasoning: whether the exchange is kept in Odoo is a
      // decision about the message being written, so it must be
      // visible while writing it rather than below the editor.
      content: "The filing toggle is above the body, not under it",
      trigger:
        ".modal .o_inner_group:has(.o_field_widget[name='subject']) .o_field_widget[name='file_in_odoo']",
    },
    {
      content: "Close the composer",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "Back on the inbox with no dialog left open",
      trigger: ".o_conversation_inbox:not(:has(.modal))",
    },
    // --------------------------------------------------------------
    // Mailbox-side triage from collapsed rows: Mark read, Archive,
    // Delete and Hide are four distinct buttons, and only Hide is
    // client-side. The Python harness stubs the transport hooks, so no
    // socket opens.
    // --------------------------------------------------------------
    {
      content: "Mark read A",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message A')) .o_inbox_mark_read",
      run: "click",
    },
    {
      content: "Mark read confirmed",
      trigger: ".o_notification:contains('Marked as read')",
    },
    {
      content: "Row A is still listed after Mark read, still collapsed",
      trigger:
        ".o_conversation_inbox_list:not(:has(.card-body)) .card-header:contains('Tour Message A')",
    },
    {
      content: "Archive A",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message A')) .o_inbox_archive",
      run: "click",
    },
    {
      content: "Row A disappears after Archive",
      trigger:
        ".o_conversation_inbox_list:not(:has(.card-header:contains('Tour Message A'))):not(:has(.card-body))",
    },
    // --------------------------------------------------------------
    // Opening a row is unchanged: it round-trips fetch_envelope and
    // renders the body as HTML.
    // --------------------------------------------------------------
    {
      content: "Expand B",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message B')",
      run: "click",
    },
    {
      // A rendered paragraph, not its escaped source: matching the text
      // alone also passed while the body was shown as raw HTML.
      content: "The envelope body rendered as HTML",
      trigger:
        ".o_conversation_inbox_body:not(:contains('<p>')) p:contains('the quote you asked for')",
    },
    {
      content: "Attachment names are listed without being ingested",
      trigger: ".o_conversation_inbox_attachments:contains('quote.pdf')",
    },
    {
      content: "The actions are still on the expanded row",
      trigger: ".o_inbox_row:has(.card-body) .o_inbox_row_actions .o_inbox_delete",
    },
    {
      content: "Delete B asks for confirmation",
      trigger: ".o_inbox_row:has(.card-body) .o_inbox_delete",
      run: "click",
    },
    {
      content: "The confirmation dialog is up",
      trigger: ".modal footer button:contains('Delete')",
    },
    {
      content: "Cancel the delete",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "Row B is still listed after cancelling",
      trigger:
        ".o_conversation_inbox:not(:has(.modal)) .o_conversation_inbox_list .card-header:contains('Tour Message B')",
    },
    {
      content: "Delete B again",
      trigger: ".o_inbox_row:has(.card-body) .o_inbox_delete",
      run: "click",
    },
    {
      content: "Confirm the delete",
      trigger: ".modal footer button:contains('Delete')",
      run: "click",
    },
    {
      content: "Row B disappears after the confirmed Delete",
      // A and B were the whole of page 1, so the list is now empty.
      trigger:
        ".o_conversation_inbox:not(:has(.modal)):contains('No messages on this page.')",
    },
    {
      content: "Page forward",
      trigger: ".o_conversation_inbox button:contains('Next'):not(:disabled)",
      run: "click",
    },
    {
      content: "Hide C from the collapsed row",
      trigger:
        ".o_inbox_row:has(.card-header:contains('Tour Message C')) .o_inbox_hide",
      run: "click",
    },
    {
      content: "Row C disappears after Hide",
      trigger: ".o_conversation_inbox:contains('No messages on this page.')",
    },
    {
      content: "Page back",
      trigger: ".o_conversation_inbox button:contains('Previous'):not(:disabled)",
      run: "click",
    },
    {
      content: "Neither A nor B is listed: the mailbox really lost them",
      trigger: ".o_conversation_inbox:contains('No messages on this page.')",
    },
  ],
});
