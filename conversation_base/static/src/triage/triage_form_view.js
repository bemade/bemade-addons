// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {FormController} from "@web/views/form/form_controller";
import {formView} from "@web/views/form/form_view";
import {registry} from "@web/core/registry";
import {useEffect} from "@odoo/owl";

/**
 * Conversation form: loading a conversation that is unread for the
 * current user marks it read for that user only, however it was opened
 * (list row, link, reload, notification, pager, redirect after filing).
 */
export class TriageFormController extends FormController {
  setup() {
    super.setup();
    useEffect(
      (resId, unread) => {
        if (resId && unread) {
          this._markRead(resId);
        }
      },
      () => [this.model.root.resId, this.model.root.data.my_unread]
    );
  }

  _markRead(resId) {
    this._markingRead = this.orm
      .call("mail.conversation", "action_triage_mark_read", [[resId]])
      .catch((error) => {
        // Never block reading the conversation on a bookkeeping failure.
        console.error("Could not mark the conversation read", error);
      });
  }

  async beforeLeave(options) {
    // The list we go back to must reflect the read state.
    await this._markingRead;
    return super.beforeLeave(options);
  }
}

export const triageFormView = {
  ...formView,
  Controller: TriageFormController,
};

registry.category("views").add("conversation_triage_form", triageFormView);
