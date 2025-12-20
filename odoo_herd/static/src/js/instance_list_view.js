/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

export class InstanceListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    // Override the create method to open wizard instead
    async createRecord() {
        await this.actionService.doAction("odoo_herd.action_k8s_create_instance_wizard");
    }
}

export const instanceListView = {
    ...listView,
    Controller: InstanceListController,
};

registry.category("views").add("instance_list", instanceListView);
