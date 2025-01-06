/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";

class UnifiDashboardController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    /**
     * @override
     */
    getRendererProps() {
        const props = super.getRendererProps();
        return {
            ...props,
            onRefreshDashboard: this.onRefreshDashboard.bind(this),
        };
    }

    async onRefreshDashboard() {
        await this.model.load();
        await this.model.root.load();
        this.render(true);
    }
}

class UnifiDashboardRenderer extends KanbanRenderer {
    static template = 'odoo_unifi_manager.UnifiDashboard';
    static components = { Layout };
    
    static props = {
        ...KanbanRenderer.props,
        onRefreshDashboard: Function,
    };

    setup() {
        super.setup();
        this.chartInstances = {};
        
        onMounted(() => {
            this.initCharts();
        });

        onWillUnmount(() => {
            // Cleanup charts
            Object.values(this.chartInstances).forEach(chart => chart.destroy());
        });
    }

    initCharts() {
        if (!this.props.list.records.length) return;
        
        const record = this.props.list.records[0];
        if (!record) return;

        // Clean up existing charts
        Object.values(this.chartInstances).forEach(chart => chart.destroy());
        this.chartInstances = {};

        // Initialize Client Type Chart
        const ctxClients = document.getElementById('clientTypeChart')?.getContext('2d');
        if (ctxClients) {
            this.chartInstances.clientType = new Chart(ctxClients, {
                type: 'doughnut',
                data: record.data.client_type_chart,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // Initialize Bandwidth Chart
        const ctxBandwidth = document.getElementById('bandwidthChart')?.getContext('2d');
        if (ctxBandwidth) {
            this.chartInstances.bandwidth = new Chart(ctxBandwidth, {
                type: 'line',
                data: record.data.bandwidth_chart,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Mbps'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }
}

export const unifiDashboardView = {
    ...kanbanView,
    Controller: UnifiDashboardController,
    Renderer: UnifiDashboardRenderer,
    buttonTemplate: 'odoo_unifi_manager.UnifiDashboard.Buttons',
};

registry.category("views").add("unifi_dashboard", unifiDashboardView);
