// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {X2ManyField, x2ManyField} from "@web/views/fields/x2many/x2many_field";
import {registry} from "@web/core/registry";

/**
 * The conversation's "Drafts" page. An active draft opens in the same
 * editable reply pop-up as Reply; a sent or discarded one keeps opening
 * read-only.
 */
export class ConversationDraftListField extends X2ManyField {
  async openRecord(record) {
    if (record.resId && record.data.state === "draft") {
      const {orm, action} = this.env.services;
      const dialogAction = await orm.call(
        "mail.conversation.draft",
        "action_open_dialog",
        [[record.resId]]
      );
      await action.doAction(dialogAction, {
        onClose: () => this.props.record.load(),
      });
      return;
    }
    return super.openRecord(record);
  }
}

registry.category("fields").add("conversation_draft_list", {
  ...x2ManyField,
  component: ConversationDraftListField,
});
