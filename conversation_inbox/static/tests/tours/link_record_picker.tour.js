// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Server state is asserted by TestLinkRecordPickerTour (tests/test_link_record_picker_tour.py).
import {registry} from "@web/core/registry";
import steps from "./link_record_picker.steps";
import {toTourStep} from "./to_tour_step";

registry.category("web_tour.tours").add("conversation_inbox_link_record_picker_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => steps.filter((step) => !step.videoOnly).map(toTourStep),
});
