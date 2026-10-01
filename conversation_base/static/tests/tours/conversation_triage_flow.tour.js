import {registry} from "@web/core/registry";
import steps from "./conversation_triage_flow.steps";

const toTourStep = (step) => {
  const tourStep = {
    content: step.title,
    trigger: step.containsText
      ? `${step.selector}:contains("${step.containsText}")`
      : step.selector,
  };
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
};

registry.category("web_tour.tours").add("conversation_triage_flow", {
  url: "/odoo/action-conversation_base.mail_conversation_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
