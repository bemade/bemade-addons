import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Subject in bold when unread, plus a one-line snippet of the latest
 * message. The empty ``o_conversation_draft_slot`` is reserved for the
 * shared-draft indicator (#3969). */
export class ConversationSubjectField extends Component {
    static template = "conversation_base.ConversationSubjectField";
    static props = { ...standardFieldProps };

    get unread() {
        return Boolean(this.props.record.data.my_unread);
    }

    get preview() {
        return this.props.record.data.last_message_preview || "";
    }
}

registry.category("fields").add("conversation_subject", {
    component: ConversationSubjectField,
    supportedTypes: ["char"],
    fieldDependencies: [
        { name: "my_unread", type: "boolean" },
        { name: "last_message_preview", type: "char" },
    ],
});
