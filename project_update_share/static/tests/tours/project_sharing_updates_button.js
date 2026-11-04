// Copyright 2026 Bemade Inc. License LGPL-3.0 or later.
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("project_update_share_sharing_button", {
    steps: () => [
        {
            content: "Project Sharing shows an Updates button",
            trigger: ".o_control_panel .o_project_update_share_button",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "It lands on the project's updates, listing the one shared with me",
            trigger: ".o_project_update_share_card:contains('For the collaborator')",
        },
    ],
});
