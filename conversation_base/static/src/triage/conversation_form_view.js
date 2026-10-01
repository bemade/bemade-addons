import {FormController} from "@web/views/form/form_controller";
import {formView} from "@web/views/form/form_view";
import {registry} from "@web/core/registry";
import {useEffect} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

/**
 * Conversation form: opening an existing conversation marks it read for the
 * current user through a dedicated (read/write) RPC.
 */
export class ConversationFormController extends FormController {
  setup() {
    super.setup();
    this.markReadOrm = useService("orm");
    useEffect(
      (resId) => {
        if (resId) {
          this.markReadOrm.call("mail.conversation", "action_mark_read", [[resId]]);
        }
      },
      () => [this.model.root.resId]
    );
  }
}

registry.category("views").add("conversation_form", {
  ...formView,
  Controller: ConversationFormController,
});
