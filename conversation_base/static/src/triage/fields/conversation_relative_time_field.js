import {Component} from "@odoo/owl";
import {formatDateTime} from "@web/core/l10n/dates";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

/** "3 hours ago" with the full date and time as tooltip. */
export class ConversationRelativeTimeField extends Component {
  static template = "conversation_base.ConversationRelativeTimeField";
  static props = {...standardFieldProps};

  get value() {
    return this.props.record.data[this.props.name];
  }

  get relative() {
    return this.value ? this.value.toRelative() : "";
  }

  get full() {
    return this.value ? formatDateTime(this.value) : "";
  }
}

registry.category("fields").add("conversation_relative_time", {
  component: ConversationRelativeTimeField,
  supportedTypes: ["datetime"],
});
