/** @odoo-module **/

import {ListController} from '@web/views/list/list_controller';
import {patch} from '@web/core/utils/patch';
import {useBus} from "@web/core/utils/hooks";

patch(ListController.prototype, {
    async setup() {
        if (this.props.archInfo.recursive) {
            this.recursive = true;
            useBus(this.env.bus, "expand-collapse-parent", this.onExpandCollapseParent);
        } else {
            this.recursive = false;
        }
        super.setup();
    },

    async onExpandCollapseParent(ev) {
        const parentId = ev.detail && typeof ev.detail === 'object' ? ev.detail.id : ev.detail;
        const record = this.model.findRecordInHierarchy(parentId);
        if (!record) {
            return;
        }
        if (record.expanded) {
            record.expanded = false;
        } else {
            await this.model._loadChildren(record);
            record.expanded = true;
        }
    },

    get modelParams() {
        const params = super.modelParams;
        if (this.recursive) {
            params["config"]["recursive"] = true;
        }
        return params;
    },

});
