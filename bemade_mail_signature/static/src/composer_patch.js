import {markup, useEffect, useState} from "@odoo/owl";
import {Composer} from "@mail/core/common/composer";
import {patch} from "@web/core/utils/patch";
import {rpc} from "@web/core/network/rpc";

/**
 * Show, in the chatter « Send message » composer, the signature block exactly
 * as the server appends it to the message (and to the email). The block comes
 * from the server so it is the same HTML, including any opt-out a module makes
 * through the notification rendering hook. Hidden in « Log note » mode.
 */
patch(Composer.prototype, {
  setup() {
    super.setup(...arguments);
    this.mailSignature = useState({block: "", key: ""});
    useEffect(
      (model, id, type) => {
        if (type === "message" && model && id && model !== "discuss.channel") {
          this.loadMailSignatureBlock(model, id);
        } else {
          this.mailSignature.key = "";
          this.mailSignature.block = "";
        }
      },
      () => [this.thread?.model, this.thread?.id, this.props.type]
    );
  },

  async loadMailSignatureBlock(model, id) {
    const key = `${model},${id}`;
    if (this.mailSignature.key === key) {
      return;
    }
    this.mailSignature.key = key;
    this.mailSignature.block = "";
    const block = await rpc("/bemade_mail_signature/block", {
      thread_model: model,
      thread_id: id,
    });
    if (this.mailSignature.key === key) {
      this.mailSignature.block = block ? markup(block) : "";
    }
  },

  get showMailSignaturePreview() {
    return Boolean(
      this.props.type === "message" &&
        !this.props.composer.message &&
        this.mailSignature.block
    );
  },

  onClickMailSignatureEdit(ev) {
    this.onClickFullComposer(ev);
  },

  onClickMailSignatureRemove() {
    this.props.composer.emailAddSignature = false;
  },

  onClickMailSignatureRestore() {
    this.props.composer.emailAddSignature = true;
  },
});
