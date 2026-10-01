import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { TriageListController } from "./triage_list_controller";
import { TriageListRenderer } from "./triage_list_renderer";

export const conversationTriageListView = {
    ...listView,
    Controller: TriageListController,
    Renderer: TriageListRenderer,
};

registry.category("views").add("conversation_triage_list", conversationTriageListView);
