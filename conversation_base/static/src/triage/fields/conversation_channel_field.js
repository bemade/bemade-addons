import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const ICONS = {
  gmail: "fa-google",
  imap: "fa-envelope",
};

/** Channel icon from the transport provider; plain "alias / email" when the
 * conversation has no transport. */
export class ConversationChannelField extends Component {
  static template = "conversation_base.ConversationChannelField";
  static props = {...standardFieldProps};

  get provider() {
    return this.props.record.data[this.props.name];
  }

  get icon() {
    return ICONS[this.provider] || (this.provider ? "fa-comments" : "fa-at");
  }

  get label() {
    if (!this.provider) {
      return _t("Alias / email");
    }
    const field = this.props.record.fields[this.props.name];
    const option = (field.selection || []).find(([key]) => key === this.provider);
    return option ? option[1] : this.provider;
  }
}

registry.category("fields").add("conversation_channel", {
  component: ConversationChannelField,
  supportedTypes: ["selection", "char"],
});
