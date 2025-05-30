/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

export class ProxmoxServerListController extends ListController {
    setup() {
        super.setup();
        this.state = {};
    }

    /**
     * @override
     */
    async getLocalState() {
        const state = await super.getLocalState();
        return { ...state, ...this.state };
    }

    /**
     * @override
     */
    async setLocalState(state) {
        if (state) {
            this.state = { ...this.state, ...state };
            await super.setLocalState(state);
        }
    }

    async onAddServer() {
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'proxmox.server.wizard',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {},
        }, {
            onClose: () => this.actionService.restore(),
        });
    }
}

ProxmoxServerListController.template = 'odoo_proxmox_manager.ProxmoxServerListView';

export const ProxmoxServerListView = {
    ...listView,
    Controller: ProxmoxServerListController,
};

registry.category("views").add("proxmox_server_list", ProxmoxServerListView);
