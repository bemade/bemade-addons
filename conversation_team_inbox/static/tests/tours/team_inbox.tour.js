// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: team_inbox
 *
 * Creates a conversation team with its alias and from address. The step
 * list is shared with the demo video. Server state is asserted by
 * TestTeamInboxTour.
 */
import {registry} from "@web/core/registry";
import steps from "./team_inbox.steps";

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

registry.category("web_tour.tours").add("team_inbox", {
  url: "/odoo/action-conversation_base.mail_conversation_team_action/new",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
