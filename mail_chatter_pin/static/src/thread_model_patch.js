// Make sure the core definition is set up first, so this one replaces it.
import "@mail/discuss/message_pin/common/thread_model_patch";
import {Thread} from "@mail/core/common/thread_model";
import {fields} from "@mail/core/common/record";
import {patch} from "@web/core/utils/patch";

/**
 * Most recently pinned first, then by id. Same order as core, but compares
 * the luxon values: core tests `m1.pinned_at === m2.pinned_at`, which is never
 * true for two DateTime objects, so two messages pinned in the same second get
 * an inconsistent order (-1 both ways), the list re-sorts forever and the tab
 * freezes.
 *
 * @param {import("models").Message} m1
 * @param {import("models").Message} m2
 */
export function comparePinnedMessages(m1, m2) {
  const t1 = m1.pinned_at.toMillis();
  const t2 = m2.pinned_at.toMillis();
  if (t1 === t2) {
    return m1.id - m2.id;
  }
  return t1 < t2 ? 1 : -1;
}

/*
 * Field definitions can only be replaced for the whole model, so this applies
 * to Discuss channels too: their order is unchanged, ties no longer hang.
 */
patch(Thread.prototype, {
  setup() {
    super.setup();
    this.pinnedMessages = fields.Many("mail.message", {
      compute() {
        return this.allMessages.filter((m) => m.pinned_at);
      },
      sort: comparePinnedMessages,
    });
  },
});
