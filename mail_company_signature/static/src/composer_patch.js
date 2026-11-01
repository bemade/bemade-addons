import {Composer} from "@mail/core/common/composer";
import {isHtmlEmpty} from "@web/core/utils/html";
import {patch} from "@web/core/utils/patch";

patch(Composer.prototype, {
  get signatureUser() {
    return this.thread?.effectiveSelf?.main_user_id;
  },
  get showSignaturePreview() {
    return Boolean(
      this.props.type === "message" &&
        !this.props.composer.message &&
        this.thread &&
        this.thread.model !== "discuss.channel" &&
        !isHtmlEmpty(this.signatureUser?.signature)
    );
  },
  get signatureBlock() {
    return this.signatureUser?.getSignatureBlock() ?? "";
  },
  onClickRemoveSignature() {
    this.props.composer.emailAddSignature = false;
  },
  onClickRestoreSignature() {
    this.props.composer.emailAddSignature = true;
  },
});
