/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class K8sDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
        
        this.state = useState({
            clusters: [],
            instances: [],
            stats: {
                total_clusters: 0,
                connected_clusters: 0,
                total_instances: 0,
                running_instances: 0,
            },
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            
            // Load clusters
            const clusters = await this.rpc("/web/dataset/call_kw", {
                model: "k8s.cluster",
                method: "search_read",
                args: [[]],
                kwargs: {
                    fields: ["name", "connection_status", "total_instances", "running_instances", "last_sync"],
                },
            });

            // Load recent instances
            const instances = await this.rpc("/web/dataset/call_kw", {
                model: "k8s.odoo.instance",
                method: "search_read",
                args: [[]],
                kwargs: {
                    fields: ["name", "cluster_id", "namespace", "phase", "url", "last_updated"],
                    limit: 10,
                    order: "last_updated desc",
                },
            });

            // Calculate stats
            const stats = {
                total_clusters: clusters.length,
                connected_clusters: clusters.filter(c => c.connection_status === 'connected').length,
                total_instances: clusters.reduce((sum, c) => sum + c.total_instances, 0),
                running_instances: clusters.reduce((sum, c) => sum + c.running_instances, 0),
            };

            this.state.clusters = clusters;
            this.state.instances = instances;
            this.state.stats = stats;
            
        } catch (error) {
            this.notification.add("Failed to load dashboard data", { type: "danger" });
            console.error("Dashboard load error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async refreshDashboard() {
        await this.loadDashboardData();
        this.notification.add("Dashboard refreshed", { type: "success" });
    }

    async syncAllClusters() {
        try {
            await this.rpc("/web/dataset/call_kw", {
                model: "k8s.cluster",
                method: "search_read",
                args: [[["active", "=", true]]],
                kwargs: { fields: ["id"] },
            }).then(async (clusters) => {
                for (const cluster of clusters) {
                    await this.rpc("/web/dataset/call_kw", {
                        model: "k8s.cluster",
                        method: "sync_odoo_instances",
                        args: [cluster.id],
                        kwargs: {},
                    });
                }
            });
            
            this.notification.add("All clusters synced successfully", { type: "success" });
            await this.loadDashboardData();
            
        } catch (error) {
            this.notification.add("Failed to sync clusters", { type: "danger" });
            console.error("Sync error:", error);
        }
    }

    openClusters() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "k8s.cluster",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            name: "Kubernetes Clusters",
        });
    }

    openInstances() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "k8s.odoo.instance",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            name: "Odoo Instances",
        });
    }

    openInstance(instanceId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "k8s.odoo.instance",
            res_id: instanceId,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    getClusterStatusClass(status) {
        return `k8s_cluster_status ${status}`;
    }

    getInstancePhaseClass(phase) {
        return `k8s_instance_phase ${phase.toLowerCase()}`;
    }

    formatDateTime(datetime) {
        if (!datetime) return "Never";
        return new Date(datetime).toLocaleString();
    }
}

K8sDashboard.template = "k8s_odoo_manager.Dashboard";

registry.category("actions").add("k8s_dashboard", K8sDashboard);
