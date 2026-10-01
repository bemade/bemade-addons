import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const MAX_SHOWN = 4;

/** Participants of a conversation as a stack of avatars. A participant with a
 * partner shows the partner's avatar; a bare address shows an initial, with
 * the address as tooltip. At most four are shown, then "+N". */
export class ConversationParticipantsField extends Component {
    static template = "conversation_base.ConversationParticipantsField";
    static props = { ...standardFieldProps };

    get participants() {
        const list = this.props.record.data[this.props.name];
        return (list ? list.records : []).map((record) => {
            const partner = record.data.partner_id;
            const partnerId = Array.isArray(partner) ? partner[0] : partner && partner.id;
            const label =
                record.data.email ||
                (Array.isArray(partner) ? partner[1] : partner && partner.display_name) ||
                "";
            return {
                id: record.resId || record.id,
                partnerId: partnerId || false,
                label,
                initial: (label.trim()[0] || "?").toUpperCase(),
            };
        });
    }

    get shown() {
        return this.participants.slice(0, MAX_SHOWN);
    }

    get extra() {
        return Math.max(0, this.participants.length - MAX_SHOWN);
    }
}

registry.category("fields").add("conversation_participants", {
    component: ConversationParticipantsField,
    supportedTypes: ["one2many"],
    relatedFields: [
        { name: "partner_id", type: "many2one", relation: "res.partner" },
        { name: "email", type: "char" },
    ],
});
