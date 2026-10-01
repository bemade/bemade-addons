import {useEffect, useState} from "@odoo/owl";
import {ListRenderer} from "@web/views/list/list_renderer";

/**
 * Conversation list renderer: marks the keyboard-focused row (state shared by
 * the controller through ``env.triage``) and keeps it scrolled into view.
 */
export class TriageListRenderer extends ListRenderer {
  setup() {
    super.setup();
    this.triage = useState(this.env.triage || {focusedResId: false});
    useEffect(
      () => {
        const row = this.tableRef.el?.querySelector(".o_conversation_row_focused");
        if (row && row.scrollIntoView) {
          row.scrollIntoView({block: "nearest"});
        }
      },
      () => [this.triage.focusedResId, this.props.list.records.length]
    );
  }

  getRowClass(record) {
    const classes = super.getRowClass(record);
    if (this.triage.focusedResId && record.resId === this.triage.focusedResId) {
      return `${classes} o_conversation_row_focused`;
    }
    return classes;
  }
}
