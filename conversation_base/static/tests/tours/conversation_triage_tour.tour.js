// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_triage_tour
 *
 * Drives the triage list the way a user does: row content, then every
 * triage action on a single row, then a bulk action on a subset. The step
 * list is shared with the demo video. Server state is asserted by
 * TestConversationTriageTour.
 */
import {registry} from "@web/core/registry";
import steps from "./conversation_triage_tour.steps";

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

registry.category("web_tour.tours").add("conversation_triage_tour", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
