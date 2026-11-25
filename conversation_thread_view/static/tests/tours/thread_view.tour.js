// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tours: thread_view
 *
 * The optional email-thread layout of a conversation. The step list of the
 * main tour is shared with the demo video.
 */
import {registry} from "@web/core/registry";
import steps from "./thread_view.steps";

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

registry.category("web_tour.tours").add("thread_view", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});

// Switching views only: list -> form -> thread view -> form. The server side
// asserts nothing was written.
registry.category("web_tour.tours").add("thread_view_switch_only", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => [
    {
      content: "Open the conversation",
      trigger:
        ".o_list_renderer tr.o_data_row td[name='name']:contains('Retard de livraison')",
      run: "click",
    },
    {
      content: "Open the thread view",
      trigger: ".o_form_view button[name='action_open_thread_view']",
      run: "click",
    },
    {
      content: "The thread is shown",
      trigger: ".o-conversationThreadView .o-mail-Message",
    },
    {
      content: "Breadcrumb goes back to the form",
      trigger: ".o_control_panel .breadcrumb-item:contains('Retard de livraison')",
      run: "click",
    },
    {
      content: "The form is back",
      trigger: ".o_form_view button[name='action_open_thread_view']",
    },
  ],
});
