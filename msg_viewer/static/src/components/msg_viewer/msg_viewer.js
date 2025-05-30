/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

export class MsgViewerAction extends Component {
    static template = "msg_viewer.Viewer";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        console.log("MsgViewerAction setup", this.props);

        onMounted(() => this.initMsgViewer());
    }

    async initMsgViewer() {
        try {
            console.log("Initializing MSG viewer");
            const { model, id, filename } = this.props.action.params;
            console.log("Params:", { model, id, filename });
            
            // Get the MSG file content from the server
            console.log("Fetching content from server...");
            const data = await this.orm.call(
                model,
                'read',
                [[id], ['datas']],
                { context: { bin_size: false } }
            );
            console.log("Got data from server:", data);

            if (!data || !data.length || !data[0].datas) {
                throw new Error("No data received from server");
            }

            // Initialize the MSG viewer
            console.log("Creating viewer instance...");
            const container = this.el.querySelector("#msg-viewer-container");
            console.log("Container:", container);

            if (!container) {
                throw new Error("MSG viewer container not found");
            }

            if (!window.MsgViewer) {
                throw new Error("MSG viewer library not loaded");
            }

            const viewer = new window.MsgViewer({
                data: data[0].datas,
                container: container,
            });
            console.log("Viewer instance created:", viewer);

        } catch (error) {
            console.error("Error initializing MSG viewer:", error);
            this.notification.add(_t("Failed to initialize MSG viewer"), {
                type: "danger",
            });
            // Close the modal
            this.action.doAction({ type: "ir.actions.act_window_close" });
        }
    }
}

registry.category("actions").add("msg_viewer", MsgViewerAction);
