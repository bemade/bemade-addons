import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";

/**
 * The native "Send message" button opens a composer that posts through the
 * notification pipeline, which never emails anyone on a conversation or on its
 * reply draft (the notification-safety invariant). Replies go through the
 * conversation's Reply button and the draft's own Send button, so the button
 * is hidden on both. "Log note" and every other model keep the stock
 * behaviour.
 */
const MODELS_WITHOUT_SEND_MESSAGE = ["mail.conversation", "mail.conversation.draft"];

patch(Chatter.prototype, {
  get hideSendMessage() {
    return MODELS_WITHOUT_SEND_MESSAGE.includes(this.state.thread?.model);
  },

  toggleComposer(mode = false, options = {}) {
    if (mode === "message" && this.hideSendMessage) {
      return;
    }
    return super.toggleComposer(mode, options);
  },
});
