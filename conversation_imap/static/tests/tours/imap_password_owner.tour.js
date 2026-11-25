// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {registry} from "@web/core/registry";
import steps from "./imap_password_owner.steps";

function toTourStep(step) {
  let trigger = step.selector;
  if (step.containsText) {
    trigger += `:contains("${step.containsText}")`;
  }
  const tourStep = {content: step.title, trigger};
  if (step.action === "click") {
    tourStep.run = "click";
  } else if (step.action === "fill") {
    tourStep.run = `edit ${step.value}`;
  } else if (step.action === "selectByLabel") {
    tourStep.run = `selectByLabel ${step.value}`;
  }
  if (step.navigates) {
    tourStep.expectUnloadPage = true;
  }
  return tourStep;
}

registry.category("web_tour.tours").add("imap_password_owner", {
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
