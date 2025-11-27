/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const AUTO_REFRESH_INTERVAL = 30000; // 30 seconds

export class K8sDashboard extends Component {
    static template = "k8s_odoo_manager.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            clusters: [],
            instances: [],
            alerts: [],
            loading: true,
            lastRefresh: null,
            autoRefresh: true,
        });
        this.refreshInterval = null;

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.startAutoRefresh();
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
        });
    }

    startAutoRefresh() {
        if (this.refreshInterval) return;
        this.refreshInterval = setInterval(async () => {
            if (this.state.autoRefresh && !this.state.loading) {
                await this.loadData();
            }
        }, AUTO_REFRESH_INTERVAL);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
    }

    async loadData(syncClusters = false) {
        this.state.loading = true;
        try {
            // Optionally sync all clusters first
            if (syncClusters) {
                await this.orm.call("k8s.cluster", "action_sync_all_instances", []);
            }
            
            const response = await fetch("/k8s/dashboard/data", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({}),
            });
            const result = await response.json();
            if (result.result) {
                this.state.clusters = result.result.clusters;
                this.state.instances = result.result.instances;
                this.state.alerts = result.result.alerts;
            }
            this.state.lastRefresh = new Date().toLocaleTimeString();
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        }
        this.state.loading = false;
    }

    async refresh() {
        // Manual refresh syncs clusters
        await this.loadData(true);
    }

    formatLastBackup(isoString) {
        if (!isoString) return "Never";
        try {
            const dt = new Date(isoString);
            const now = new Date();
            const diffMs = now - dt;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 60) {
                return `${diffMins} min ago`;
            } else if (diffHours < 24) {
                return `${diffHours}h ago`;
            } else {
                return `${diffDays}d ago`;
            }
        } catch (e) {
            return "Unknown";
        }
    }

    getStatusClass(connected) {
        return connected ? "text-success" : "text-danger";
    }

    getStatusIcon(connected) {
        return connected ? "fa-check-circle" : "fa-times-circle";
    }

    getAlertClass(type) {
        return `alert-${type}`;
    }

    // Navigation actions
    viewClusterInstances(clusterId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Instances",
            res_model: "k8s.odoo.instance",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["cluster_id", "=", clusterId]],
        });
    }

    viewClusterBackups(clusterId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Backups",
            res_model: "k8s.odoo.backup",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["cluster_id", "=", clusterId]],
        });
    }

    createInstance(clusterId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Create Instance",
            res_model: "k8s.create.instance.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_cluster_id: clusterId },
        });
    }

    async syncCluster(clusterId) {
        await this.orm.call("k8s.cluster", "action_sync_instances", [clusterId]);
        await this.loadData();
    }

    openInstance(instanceId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Instance",
            res_model: "k8s.odoo.instance",
            res_id: instanceId,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    openInstanceUrl(url) {
        window.open(url, "_blank");
    }
}

registry.category("actions").add("k8s_dashboard", K8sDashboard);
