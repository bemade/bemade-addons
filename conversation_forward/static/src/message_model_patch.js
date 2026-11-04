import {Message} from "@mail/core/common/message_model";
import {patch} from "@web/core/utils/patch";

/**
 * Odoo's native Forward (and, through canReplyAll, Reply-All) open
 * mail.compose.message, which emails external partners through the
 * notification pipeline. That is forbidden on conversations (the
 * notification-safety invariant), so hide both there. Every other model
 * keeps the stock behaviour.
 */
patch(Message.prototype, {
  canForward(thread) {
    if (thread?.model === "mail.conversation") {
      return false;
    }
    return super.canForward(thread);
  },
});
