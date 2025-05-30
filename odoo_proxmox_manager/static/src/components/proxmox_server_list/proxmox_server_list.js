/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

class ProxmoxServerListController extends ListController {
    setup() {
        super.setup();
    }

    async onAddServer() {
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'proxmox.server.wizard',
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {},
        });
    }
}

ProxmoxServerListController.template = 'odoo_proxmox_manager.ProxmoxServerListView.Buttons';

export const proxmoxServerList = {
    ...listView,
    Controller: ProxmoxServerListController,
};

registry.category("views").add("proxmox_server_list", proxmoxServerList);
