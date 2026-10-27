// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: draft_signature
 *
 * Opens a reply on a conversation without a team inbox, checks the user's signature is already in the editable body, then sends.
 * The step list is shared with the demo video.
 */
import {registry} from "@web/core/registry";
import steps from "./draft_signature.steps";

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

registry.category("web_tour.tours").add("draft_signature", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
