/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef } from "@odoo/owl";

class ProxmoxDashboardController extends Component {
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.serverData = {};
        this.chartRefs = {};
        
        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        const serverData = await this.orm.call(
            'proxmox.server',
            'get_dashboard_data',
            []
        );
        this.serverData = serverData;
        this.render();
    }

    openServers() {
        this.actionService.doAction('odoo_proxmox_manager.action_proxmox_server');
    }

    openClusters() {
        this.actionService.doAction('odoo_proxmox_manager.action_proxmox_cluster');
    }

    openVMs() {
        this.actionService.doAction('odoo_proxmox_manager.action_proxmox_vm');
    }
}

ProxmoxDashboardController.template = 'odoo_proxmox_manager.DashboardView';
ProxmoxDashboardController.components = { Layout };

registry.category("actions").add("proxmox_dashboard_client_action", {
    type: "ir.actions.client",
    tag: "proxmox_dashboard",
    target: "main",
    Component: ProxmoxDashboardController,
});
