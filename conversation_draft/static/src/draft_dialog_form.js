// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {FormController} from "@web/views/form/form_controller";
import {formView} from "@web/views/form/form_view";
import {registry} from "@web/core/registry";

/**
 * The reply pop-up. Closing it without sending (the X, Escape or "Close")
 * must never lose what was typed: a stock form dialog discards unsaved
 * changes, this one saves them first. The draft stays active and reopening
 * Reply shows the same content.
 */
export class ConversationDraftDialogController extends FormController {
  setup() {
    super.setup();
    if (this.env.dialogData) {
      this.env.dialogData.dismiss = () => this.saveBeforeClose();
    }
  }

  async saveBeforeClose() {
    const record = this.model.root;
    if (record.dirty) {
      try {
        await record.save({reload: false});
      } catch {
        // Leave the draft as it was last saved rather than trap the user in
        // the pop-up.
      }
    }
  }

  async beforeExecuteActionButton(clickParams) {
    if (clickParams.special === "cancel") {
      await this.saveBeforeClose();
      return;
    }
    return super.beforeExecuteActionButton(clickParams);
  }
}

registry.category("views").add("conversation_draft_dialog_form", {
  ...formView,
  Controller: ConversationDraftDialogController,
});
