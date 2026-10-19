import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";

/**
 * The native "Send message" button opens a composer that posts through the
 * notification pipeline, which never emails anyone on a conversation (the
 * notification-safety invariant). Replies go through the conversation's Reply
 * button and its shared draft, so the button is hidden there. "Log note" and
 * every other model keep the stock behaviour.
 */
patch(Chatter.prototype, {
  get hideSendMessage() {
    return this.state.thread?.model === "mail.conversation";
  },

  toggleComposer(mode = false, options = {}) {
    if (mode === "message" && this.hideSendMessage) {
      return;
    }
    return super.toggleComposer(mode, options);
  },
});
