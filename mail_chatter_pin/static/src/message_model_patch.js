import {Message} from "@mail/core/common/message_model";
import {patch} from "@web/core/utils/patch";

export const PINNABLE_MESSAGE_TYPES = ["comment", "email", "email_outgoing"];

patch(Message.prototype, {
  /**
   * Whether this message can be (un)pinned on the record chatter it belongs
   * to. Discuss channels keep the core pin feature.
   *
   * @param {import("models").Thread} [thread] the thread it is shown in
   */
  canChatterPin(thread) {
    const recordThread = this.thread;
    return Boolean(
      recordThread &&
        (!thread || thread.eq(recordThread)) &&
        !["discuss.channel", "mail.box"].includes(recordThread.model) &&
        Number.isInteger(recordThread.id) &&
        Number.isInteger(this.id) &&
        this.store.self_partner?.main_user_id?.share === false &&
        recordThread.hasWriteAccess &&
        PINNABLE_MESSAGE_TYPES.includes(this.message_type) &&
        !this.isEmpty
    );
  },

  /** (Un)pin this message on its record chatter; silent, no confirmation. */
  async chatterTogglePin() {
    const thread = this.thread;
    const data = await this.store.env.services.orm.call(
      thread.model,
      "message_set_pin",
      [[thread.id]],
      {message_id: this.id, pinned: !this.pinned_at}
    );
    this.store.insert(data);
  },
});
