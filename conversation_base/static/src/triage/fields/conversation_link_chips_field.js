import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** One chip per linked record. Clicking opens the target's form without
 * opening the row; a target the user cannot read (or that is gone) renders as
 * a neutral, non-clickable chip. */
export class ConversationLinkChipsField extends Component {
    static template = "conversation_base.ConversationLinkChipsField";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
    }

    get chips() {
        const list = this.props.record.data[this.props.name];
        return (list ? list.records : []).map((record) => ({
            id: record.resId || record.id,
            resModel: record.data.res_model,
            resId: record.data.res_id,
            accessible: Boolean(record.data.record_accessible),
            label: record.data.record_accessible
                ? record.data.record_display_name
                : _t("Linked record"),
        }));
    }

    onClickChip(ev, chip) {
        ev.stopPropagation();
        if (!chip.accessible) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: chip.resModel,
            res_id: chip.resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("fields").add("conversation_link_chips", {
    component: ConversationLinkChipsField,
    supportedTypes: ["one2many"],
    relatedFields: [
        { name: "res_model", type: "char" },
        { name: "res_id", type: "integer" },
        { name: "record_display_name", type: "char" },
        { name: "record_accessible", type: "boolean" },
    ],
});
