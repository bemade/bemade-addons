// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {CollaborationOdooPlugin} from "@html_editor/others/collaboration/collaboration_odoo_plugin";
import {HistoryPlugin} from "@html_editor/core/history_plugin";
import {HtmlField, htmlField} from "@html_editor/fields/html_field";
import {registry} from "@web/core/registry";
import {DraftCollaborationPlugin} from "./draft_collaboration_plugin";
import {DraftHistoryPlugin} from "./draft_history_plugin";

/**
 * Odoo's editor plugins with the two the reply draft replaces: its history
 * merges concurrent typing instead of overwriting the text node, and its
 * collaboration holds input while catching up and keeps the caret with the
 * user's own text.
 *
 * @param {Array<typeof import("@html_editor/plugin").Plugin>} Plugins
 */
export function withDraftPlugins(Plugins) {
  return Plugins.map((Plugin) => {
    if (Plugin === CollaborationOdooPlugin) {
      return DraftCollaborationPlugin;
    }
    if (Plugin === HistoryPlugin) {
      return DraftHistoryPlugin;
    }
    return Plugin;
  });
}

/**
 * The reply draft body: Odoo's collaborative HTML field with the draft's
 * editor plugins (see withDraftPlugins). Held input is applied before every
 * save, so closing or sending the pop-up never drops it.
 */
export class ConversationDraftHtmlField extends HtmlField {
  getConfig() {
    const config = super.getConfig();
    if (this.props.isCollaborative) {
      config.Plugins = withDraftPlugins(config.Plugins);
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
