// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Clicks the Conversations app from the main menu, checks it lands on the
// conversation list (with the sub-menu's default facets), then that the Inbox
// is still reachable from its own menu.
import {registry} from "@web/core/registry";
import steps from "./conversation_app_landing.steps";
import {toTourStep} from "./to_tour_step";

registry.category("web_tour.tours").add("conversation_app_landing_tour", {
  url: "/odoo",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
