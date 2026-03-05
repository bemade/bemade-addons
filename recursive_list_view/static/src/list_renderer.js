/** @odoo-module **/

import { ListRenderer } from '@web/views/list/list_renderer';
import { patch } from '@web/core/utils/patch';
import { useState } from '@odoo/owl';

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.recursive = this.props.archInfo.recursive;
        useState(this.props.list.records);
    },

    async _onExpandClick(ev) {
        const raw = ev.currentTarget.dataset.expand;
        const parent = isNaN(raw) ? raw : Number(raw);
        this.env.bus.trigger("expand-collapse-parent", parent);
    },
});
