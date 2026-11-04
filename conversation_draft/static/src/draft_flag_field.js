// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

/** Pencil badge on a row whose reply is being drafted. */
export class ConversationDraftFlagField extends Component {
  static template = "conversation_draft.ConversationDraftFlagField";
  static props = {...standardFieldProps};

  get editorName() {
    const editor = this.props.record.data.draft_editor_id;
    return editor ? editor.display_name || editor[1] : false;
  }

  get label() {
    return this.editorName
      ? _t("%(user)s is replying", {user: this.editorName})
      : _t("Draft");
  }
}

export const conversationDraftFlagField = {
  component: ConversationDraftFlagField,
  displayName: _t("Draft indicator"),
  supportedTypes: ["boolean"],
};
registry.category("fields").add("conversation_draft_flag", conversationDraftFlagField);
