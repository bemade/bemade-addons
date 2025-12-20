/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class S3UploadWidget extends Component {
    static template = "odoo_herd.S3UploadWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            uploading: false,
            progress: 0,
            error: null,
            success: false,
        });
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    get uploadUrl() {
        return this.props.record.data.upload_url;
    }

    get objectKey() {
        return this.props.record.data.object_key;
    }

    async onFileChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;

        if (!this.uploadUrl) {
            this.notification.add("No upload URL available. Please generate one first.", {
                type: "danger",
            });
            return;
        }

        this.state.uploading = true;
        this.state.progress = 0;
        this.state.error = null;
        this.state.success = false;

        try {
            await this.uploadFile(file);
            this.state.success = true;
            this.notification.add(`File uploaded successfully to ${this.objectKey}`, {
                type: "success",
            });
        } catch (error) {
            this.state.error = error.message || "Upload failed";
            this.notification.add(`Upload failed: ${this.state.error}`, {
                type: "danger",
            });
        } finally {
            this.state.uploading = false;
        }
    }

    async uploadFile(file) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener("progress", (e) => {
                if (e.lengthComputable) {
                    this.state.progress = Math.round((e.loaded / e.total) * 100);
                }
            });

            xhr.addEventListener("load", () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve();
                } else {
                    reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
                }
            });

            xhr.addEventListener("error", () => {
                reject(new Error("Network error during upload"));
            });

            xhr.open("PUT", this.uploadUrl);
            xhr.send(file);
        });
    }
}

registry.category("fields").add("s3_upload", {
    component: S3UploadWidget,
    supportedTypes: ["char"],
});
