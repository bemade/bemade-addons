// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {registry} from "@web/core/registry";
import steps from "./inbox_local_time.steps";
import {toTourStep} from "./to_tour_step";

registry.category("web_tour.tours").add("conversation_inbox_local_time_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => [
    {
      // The test browser runs in UTC; a Toronto user's browser does not.
      content: "View the inbox from a Toronto browser",
      trigger: ".o_conversation_inbox",
      run() {
        window.luxon.Settings.defaultZone = "America/Toronto";
      },
    },
    {
      // Rows already on screen were drawn in UTC; paging away and back
      // draws them again in the new zone.
      content: "Page forward",
      trigger: ".o_conversation_inbox button:contains('Next'):not(:disabled)",
      run: "click",
    },
    {
      content: "Page 2 is up",
      trigger:
        ".o_conversation_inbox_list .card-header:contains('Second Page Message')",
    },
    {
      content: "Page back",
      trigger: ".o_conversation_inbox button:contains('Previous'):not(:disabled)",
      run: "click",
    },
    ...steps.filter((step) => !step.videoOnly).map(toTourStep),
  ],
});
