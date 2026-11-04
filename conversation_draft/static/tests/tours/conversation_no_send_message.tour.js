// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_no_send_message
 *
 * On a conversation the chatter offers "Log note" but no "Send message".
 * The step list is shared with the demo video.
 */
import {registry} from "@web/core/registry";
import steps from "./conversation_no_send_message.steps";

function toTourStep(step) {
  const out = {content: step.title, trigger: step.selector};
  if (step.containsText) {
    out.trigger += `:contains('${step.containsText}')`;
  }
  if (step.action === "click") {
    out.run = "click";
  } else if (step.action === "fill") {
    out.run = `edit ${step.value}`;
  } else if (step.action === "selectByLabel") {
    out.run = `selectByLabel ${step.value}`;
  }
  if (step.navigates) {
    out.expectUnloadPage = true;
  }
  return out;
}

registry.category("web_tour.tours").add("conversation_no_send_message", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});

// Soft-launch guard: any other model keeps its "Send message" button.
registry.category("web_tour.tours").add("conversation_send_message_other_model", {
  steps: () => [
    {
      content: "Log note is offered on another model",
      trigger: ".o-mail-Chatter-topbar .o-mail-Chatter-logNote",
    },
    {
      content: "Send message is still offered on another model",
      trigger: ".o-mail-Chatter-topbar .o-mail-Chatter-sendMessage",
    },
  ],
});
