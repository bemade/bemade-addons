// Registers the "send an email with the company signature" flow as a web_tour,
// mapped from the shared step list in send_with_signature.steps.js. Video-only
// steps are skipped here.
import {registry} from "@web/core/registry";
import STEPS from "./send_with_signature.steps";

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
      break;
    default:
      throw new Error(`Unsupported tour action: ${step.action}`);
  }
  if (step.navigates) {
    tourStep.expectUnloadPage = true;
  }
  return tourStep;
}

registry.category("web_tour.tours").add("mail_company_signature_send_flow", {
  steps: () => STEPS.filter((s) => !s.videoOnly).map(toTourStep),
});
