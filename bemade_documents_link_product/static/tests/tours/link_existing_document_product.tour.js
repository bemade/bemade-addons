import {registry} from "@web/core/registry";
import steps from "./link_existing_document_product.steps";

function toTourStep(step) {
  const trigger = step.containsText
    ? `${step.selector}:contains('${step.containsText}')`
    : step.selector;
  const out = {trigger, content: step.title};
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

registry.category("web_tour.tours").add("link_existing_document_product", {
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
