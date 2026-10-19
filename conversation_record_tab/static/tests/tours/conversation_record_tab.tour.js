// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tours: conversation_record_tab
 *
 * - conversation_record_tab: a record with linked conversations shows the
 *   tab with the right count, a row opens the conversation. The step list is
 *   shared with the demo video.
 * - conversation_record_tab_empty: a record without link shows no tab.
 */
import {registry} from "@web/core/registry";
import steps from "./conversation_record_tab.steps";

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

const START_URL = "/odoo/action-base.action_partner_form";

registry.category("web_tour.tours").add("conversation_record_tab", {
  url: START_URL,
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});

registry.category("web_tour.tours").add("conversation_record_tab_empty", {
  url: START_URL,
  steps: () => [
    {
      content: "Open a record without linked conversation",
      trigger: ".o_data_row td.o_data_cell:contains('Client Sans Lien')",
      run: "click",
    },
    {
      content: "Wait for the chatter to be loaded",
      trigger: ".o-mail-Chatter .o-mail-Chatter-topbar",
      // Leave time for the (empty) tab request to come back.
      run: async () => await new Promise((resolve) => setTimeout(resolve, 1000)),
    },
    {
      content: "No tab for a record without linked conversation",
      trigger: ".o-mail-Chatter:not(:has(.o_relevant_conversations_toggle))",
    },
  ],
});
