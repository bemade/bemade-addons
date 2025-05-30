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
        const $button = $(ev.currentTarget);
        const parent = $button.data('expand');
        this.env.bus.trigger("expand-collapse-parent", parent);
    },
});
