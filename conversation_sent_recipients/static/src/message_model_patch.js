import {Message} from "@mail/core/common/message_model";
import {fields} from "@mail/model/misc";
import {patch} from "@web/core/utils/patch";

/**
 * The To and Cc addresses recorded when a mail was sent from a conversation.
 * The server only sends them for messages of a conversation, and the getters
 * answer nothing for any other thread, so every other model renders as before.
 */
patch(Message.prototype, {
  setup() {
    super.setup(...arguments);
    /** @type {Array<{mode: string, email: string, name: string|false}>} */
    this.sent_recipients = fields.Attr([]);
  },
  get sentToRecipients() {
    return this._sentRecipientsOfMode("to");
  },
  get sentCcRecipients() {
    return this._sentRecipientsOfMode("cc");
  },
  _sentRecipientsOfMode(mode) {
    if (this.thread?.model !== "mail.conversation") {
      return [];
    }
    return (this.sent_recipients || []).filter((recipient) => recipient.mode === mode);
  },
});
