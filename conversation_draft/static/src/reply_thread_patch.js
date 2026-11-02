// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Thread} from "@mail/core/common/thread_model";
import {patch} from "@web/core/utils/patch";
import {reactive} from "@odoo/owl";
import {rpc} from "@web/core/network/rpc";

/**
 * Ids of the messages a conversation offers a per-message Reply on: the ones
 * a correspondent has seen. The server decides (the store carries no
 * transport information and the shared message model stays untouched), so
 * each batch of messages a conversation thread loads is checked once, before
 * the messages are rendered.
 */
export const replyTargets = reactive(new Set());

patch(Thread.prototype, {
  async fetchMessagesData() {
    const res = await super.fetchMessagesData(...arguments);
    if (this.model === "mail.conversation" && this.id && res?.messages?.length) {
      const ids = await rpc(
        "/web/dataset/call_kw/mail.conversation/reply_target_message_ids",
        {
          model: "mail.conversation",
          method: "reply_target_message_ids",
          args: [[this.id], res.messages],
          kwargs: {},
        }
      );
      for (const id of ids) {
        replyTargets.add(id);
      }
    }
    return res;
  },
});
