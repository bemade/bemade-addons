// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_open_enrols_reader_tour
 *
 * Started on a conversation's direct URL by a user with no member row on
 * it; returns to the list so the form's mark-read call has completed.
 * Server state is asserted by TestConversationOpenMarksRead.
 */
import {registry} from "@web/core/registry";
import steps from "./conversation_open_enrols_reader_tour.steps";

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

// No `url`: the test starts it on one conversation's own URL, and a tour
// url different from the start URL would redirect away from it.
registry.category("web_tour.tours").add("conversation_open_enrols_reader_tour", {
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
