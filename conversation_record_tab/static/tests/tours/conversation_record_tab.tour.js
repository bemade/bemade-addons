// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tours: conversation_record_tab
 *
 * - conversation_record_tab: a record with linked conversations shows the
 *   tab with the right count, a row opens the conversation. The step list is
 *   shared with the demo video.
 *   Tour-only checks: the exact count, and no tab on the opened
 *   conversation (which is itself the target of a link).
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

// Wait until the chatter is rendered and its (possibly empty) tab request
// has had time to come back.
const waitForChatter = () => [
  {
    content: "Wait for the chatter to be loaded",
    trigger: ".o-mail-Chatter .o-mail-Chatter-topbar",
    run: async () => await new Promise((resolve) => setTimeout(resolve, 1000)),
  },
];

// Checks the web_tour makes on top of the shared steps; they stay out of the
// demo video.
const tourOnlyAfter = () => ({
  tab: [
    {
      content: "The count is exactly the number of linked conversations",
      trigger: ".o-mail-Chatter .o_relevant_conversations_count:text(2)",
    },
  ],
  "conversation-form": [
    ...waitForChatter(),
    {
      content: "No tab on a conversation, even one linked to another conversation",
      trigger: ".o-mail-Chatter:not(:has(.o_relevant_conversations_toggle))",
    },
  ],
});

const START_URL = "/odoo/action-base.action_partner_form";

registry.category("web_tour.tours").add("conversation_record_tab", {
  url: START_URL,
  steps: () => {
    const extra = tourOnlyAfter();
    return steps
      .filter((step) => !step.videoOnly)
      .flatMap((step) => [toTourStep(step), ...(extra[step.id] || [])]);
  },
});

registry.category("web_tour.tours").add("conversation_record_tab_empty", {
  url: START_URL,
  steps: () => [
    {
      content: "Open a record without linked conversation",
      trigger: ".o_data_row td.o_data_cell:contains('Client Sans Lien')",
      run: "click",
    },
    ...waitForChatter(),
    {
      content: "No tab for a record without linked conversation",
      trigger: ".o-mail-Chatter:not(:has(.o_relevant_conversations_toggle))",
    },
  ],
});
