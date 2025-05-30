/** @odoo-module **/

import { AttachmentList } from "@mail/core/common/attachment_list";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

console.log("Loading MSG viewer patch");

patch(AttachmentList.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        console.log("MsgViewer patch setup called");
    },

    isMsgFile(attachment) {
        console.log("Checking if is MSG file:", attachment);
        return attachment.mimetype === "application/vnd.ms-outlook" || 
               (attachment.name && attachment.name.toLowerCase().endsWith('.msg'));
    },

    async openMsgViewer(attachment) {
        console.log("Opening MSG viewer for:", attachment);
        try {
            const action = {
                type: "ir.actions.client",
                tag: "msg_viewer",
                name: _t("MSG Viewer"),
                target: "new",
                params: {
                    model: "ir.attachment",
                    id: attachment.id,
                    filename: attachment.name,
                },
            };
            console.log("Executing action:", action);
            await this.action.doAction(action);
        } catch (error) {
            console.error("Error in openMsgViewer:", error);
            this.notification.add(_t("Failed to open MSG viewer"), {
                type: "danger",
            });
        }
    },
});

console.log("MSG viewer patch registered");
