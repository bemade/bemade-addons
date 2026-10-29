// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {CollaborationOdooPlugin} from "@html_editor/others/collaboration/collaboration_odoo_plugin";
import {HtmlField, htmlField} from "@html_editor/fields/html_field";
import {registry} from "@web/core/registry";
import {DraftCollaborationPlugin} from "./draft_collaboration_plugin";

/**
 * The reply draft body: Odoo's collaborative HTML field, with the draft's
 * collaboration plugin (input typed while the editor catches up with a
 * colleague is kept, see DraftCollaborationPlugin). Held input is applied
 * before every save, so closing or sending the pop-up never drops it.
 */
export class ConversationDraftHtmlField extends HtmlField {
  getConfig() {
    const config = super.getConfig();
    if (this.props.isCollaborative) {
      config.Plugins = config.Plugins.map((Plugin) =>
        Plugin === CollaborationOdooPlugin ? DraftCollaborationPlugin : Plugin
      );
    }
    return config;
  }

  async _commitChanges(params) {
    this.editor?.shared.collaborationOdoo?.flushCatchUp?.();
    return super._commitChanges(params);
  }
}

export const conversationDraftHtmlField = {
  ...htmlField,
  component: ConversationDraftHtmlField,
};

registry.category("fields").add("conversation_draft_html", conversationDraftHtmlField);
