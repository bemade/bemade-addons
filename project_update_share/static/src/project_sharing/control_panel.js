// Copyright 2026 Bemade Inc. License LGPL-3.0 or later.
// Loaded in the Project Sharing bundle only (project.webclient).
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

patch(ControlPanel.prototype, {
    /** The portal updates page of the project being shared, if any. */
    get projectUpdateShareUrl() {
        return session.project_id ? `/my/projects/${session.project_id}/updates` : "";
    },
});
