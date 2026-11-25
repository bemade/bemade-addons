import {Component, useEffect, useState} from "@odoo/owl";
import {KeepLast} from "@web/core/utils/concurrency";
import {useDebounced} from "@web/core/utils/timing";
import {useService} from "@web/core/utils/hooks";

/**
 * One read-only line under the chatter's "To:" row listing the followers the
 * message will also notify. Display only: the text is rendered (and
 * translated) by the server, from the same data as the send path.
 */
export class NotifiedPreview extends Component {
  static template = "bemade_mail_notified_preview.NotifiedPreview";
  static props = {
    thread: {type: Object},
  };

  setup() {
    this.orm = useService("orm");
    this.state = useState({line: "", warn: false});
    this.keepLast = new KeepLast();
    this.fetchDebounced = useDebounced(() => this.fetch(), 400);
    let lastKey = null;
    useEffect(
      (key) => {
        // First render: fetch right away; recipient changes: debounced.
        if (lastKey === null) {
          this.fetch();
        } else if (key !== lastKey) {
          this.fetchDebounced();
        }
        lastKey = key;
      },
      () => [this.previewKey]
    );
  }

  /** Partners already typed in To (suggested + additional recipients). */
  get excludedPartnerIds() {
    const thread = this.props.thread;
    const ids = new Set();
    for (const recipient of [
      ...(thread.suggestedRecipients || []),
      ...(thread.additionalRecipients || []),
    ]) {
      if (recipient.partner_id) {
        ids.add(recipient.partner_id);
      }
    }
    return [...ids].sort((a, b) => a - b);
  }

  /** Changes when the recipients or the followers change. Read in the template
   * so that the component re-renders (and the effect runs) on those changes. */
  get previewKey() {
    const thread = this.props.thread;
    return JSON.stringify([
      thread.model,
      thread.id,
      thread.followersCount,
      this.excludedPartnerIds,
    ]);
  }

  async fetch() {
    const thread = this.props.thread;
    if (!thread.id || !thread.model) {
      Object.assign(this.state, {line: "", warn: false});
      return;
    }
    try {
      const result = await this.keepLast.add(
        this.orm.silent.call(thread.model, "get_notified_preview", [[thread.id]], {
          exclude_partner_ids: this.excludedPartnerIds,
        })
      );
      Object.assign(this.state, {line: result.line, warn: result.warn});
    } catch {
      // Display only: never get in the way of writing the message.
      Object.assign(this.state, {line: "", warn: false});
    }
  }
}
