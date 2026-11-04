/** @odoo-module **/
// Registers the "list a model for email-only-when-addressed" flow as a
// web_tour, mapped from the shared step list in addressed_only_settings.steps.js.
// Runs as the regression test in tests/test_settings_tour.py.

import {registry} from "@web/core/registry";
import STEPS from "./addressed_only_settings.steps";

function toTourStep(step) {
  const contains = step.containsText ? `:contains(${step.containsText})` : "";
  const tourStep = {
    content: step.title,
    trigger: `${step.selector}${contains}`,
  };
  switch (step.action) {
    case "click":
      tourStep.run = "click";
      break;
    case "fill":
      tourStep.run = `edit ${step.value}`;
      break;
    case "selectByLabel":
      tourStep.run = `selectByLabel ${step.value}`;
      break;
    case "assert":
      // No run: the step passes once the trigger is present
      break;
    default:
      throw new Error(`Unsupported tour action: ${step.action}`);
  }
  if (step.navigates) {
    tourStep.expectUnloadPage = true;
  }
  return tourStep;
}

registry.category("web_tour.tours").add("mail_notification_addressed_only_settings", {
  url: "/odoo/action-base_setup.action_general_configuration",
  steps: () => STEPS.filter((s) => !s.videoOnly).map(toTourStep),
});
