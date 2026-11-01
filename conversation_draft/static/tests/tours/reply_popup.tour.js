// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tours: reply_popup
 *
 * Reply from the conversation's thread, at the top and on one email, in a
 * pop-up that keeps the user on the conversation. The step list of the main
 * tour is shared with the demo video.
 */
import {registry} from "@web/core/registry";
import steps from "./reply_popup.steps";

function toTourStep(step) {
  const out = {content: step.title, trigger: step.selector};
  if (step.containsText) {
    out.trigger += `:contains('${step.containsText}')`;
  }
  if (step.action === "click") {
    out.run = "click";
  } else if (step.action === "fill") {
    out.run = step.selector.includes(".odoo-editor-editable")
      ? `editor ${step.value}`
      : `edit ${step.value}`;
  } else if (step.action === "selectByLabel") {
    out.run = `selectByLabel ${step.value}`;
  }
  if (step.navigates) {
    out.expectUnloadPage = true;
  }
  return out;
}

registry.category("web_tour.tours").add("reply_popup", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});

// One "Reply" per email, and the native note reply stays on internal notes.
registry.category("web_tour.tours").add("reply_popup_actions", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => [
    {
      content: "Open the conversation",
      trigger:
        ".o_list_renderer tr.o_data_row td[name='name']:contains('Retard de livraison')",
      run: "click",
    },
    {
      content: "The received email offers exactly one Reply",
      trigger: ".o-mail-Message:contains('Quand ma commande arrive-t-elle ?')",
      run() {
        const count = this.anchor.querySelectorAll(
          ".o-mail-Message-actions button[title='Reply']"
        ).length;
        if (count !== 1) {
          throw new Error(`expected one Reply on the email, found ${count}`);
        }
      },
    },
    {
      content: "The internal note keeps its native reply, once",
      trigger: ".o-mail-Message:contains('Note interne')",
      run() {
        const count = this.anchor.querySelectorAll(
          ".o-mail-Message-actions button[title='Reply']"
        ).length;
        if (count !== 1) {
          throw new Error(`expected one Reply on the note, found ${count}`);
        }
      },
    },
  ],
});

// A colleague finishes the draft from the "Drafts" page, in the pop-up.
registry.category("web_tour.tours").add("reply_popup_drafts_page", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => [
    {
      content: "Open the conversation",
      trigger:
        ".o_list_renderer tr.o_data_row td[name='name']:contains('Retard de livraison')",
      run: "click",
    },
    {
      content: "Open the Drafts page",
      trigger: ".o_notebook .nav-link[name='drafts']",
      run: "click",
    },
    {
      content: "Click the pending draft",
      trigger: ".o_field_widget[name='draft_ids'] tr.o_data_row td[name='state']",
      run: "click",
    },
    {
      content: "It opens in the pop-up, editable",
      trigger: ".modal .o_field_widget[name='subject'] input:not([readonly])",
      run: "edit Rédigé par un collègue",
    },
    {
      content: "Close the pop-up",
      trigger: ".modal-footer button:contains('Close')",
      run: "click",
    },
    {
      content: "Still on the conversation",
      trigger: "body:not(:has(.modal)) .o_form_view .o_notebook",
    },
  ],
});
