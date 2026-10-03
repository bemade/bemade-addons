// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {ListController} from "@web/views/list/list_controller";
import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";

/**
 * Triage list: a plain list view whose only behavioural change is that
 * opening a row marks the conversation read for the current user.
 */
export class TriageListController extends ListController {
  async openRecord(record, options) {
    try {
      await this.orm.call("mail.conversation", "action_triage_mark_read", [
        [record.resId],
      ]);
    } catch (error) {
      // Never block opening the conversation on a bookkeeping failure.
      console.error("Could not mark the conversation read", error);
    }
    return super.openRecord(record, options);
  }
}

export const triageListView = {
  ...listView,
  Controller: TriageListController,
  props: (genericProps, view) => {
    const props = listView.props(genericProps, view);
    props.className = `${props.className || ""} o_conversation_triage_list`.trim();
    return props;
  },
};

registry.category("views").add("conversation_triage_list", triageListView);
