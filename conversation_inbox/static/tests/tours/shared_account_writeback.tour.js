// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Server state is asserted by TestSharedInboxTours (tests/test_shared_inbox_tours.py).
import {registry} from "@web/core/registry";
import steps from "./shared_account_writeback.steps";
import {toTourStep} from "./to_tour_step";

registry
  .category("web_tour.tours")
  .add("conversation_inbox_shared_account_writeback_tour", {
    url: "/odoo/action-conversation_inbox.conversation_transport_action_my",
    steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
  });
