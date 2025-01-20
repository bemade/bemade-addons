/** @odoo-module */

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FileUploader } from "@web/views/fields/file_handler";
import { Component, onWillUpdateProps, useState } from "@odoo/owl";
import { url } from "@web/core/utils/urls";
import { useService } from "@web/core/utils/hooks";

class MsgViewerField extends Component {
    static template = "web.MsgViewerField";
    static components = {
        FileUploader,
    };
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            isValid: true,
            objectUrl: "",
            showViewer: false,
        });
        onWillUpdateProps((nextProps) => {
            if (nextProps.readonly) {
                this.state.objectUrl = "";
                this.state.showViewer = false;
            }
        });
    }

    get url() {
        if (!this.state.isValid || !this.props.value) {
            return null;
        }
        const file = encodeURIComponent(
            this.state.objectUrl ||
            url("/msg_viewer/content", {
                model: this.props.record.resModel,
                field: this.props.name,
                id: this.props.record.resId,
            })
        );
        return `/msg_viewer/static/src/lib/index.html?file=${file}`;
    }

    async onFileUploaded(file) {
        this.state.objectUrl = URL.createObjectURL(file);
        await this.props.update(file);
    }

    async onFileRemove() {
        if (this.state.objectUrl) {
            URL.revokeObjectURL(this.state.objectUrl);
            this.state.objectUrl = "";
        }
        this.state.showViewer = false;
        await this.props.update(false);
    }

    openMsgViewer() {
        this.state.showViewer = true;
    }

    onLoadFailed() {
        this.notification.add(
            _t("Could not display the selected MSG file."),
            {
                type: "danger",
            }
        );
        this.state.isValid = false;
    }
}

export const msgViewerField = {
    component: MsgViewerField,
    displayName: _t("MSG Viewer"),
    supportedTypes: ["binary"],
    extractProps: ({ props }) => ({
        acceptedFileExtensions: ".msg",
    }),
};

registry.category("fields").add("msg_viewer", msgViewerField);
