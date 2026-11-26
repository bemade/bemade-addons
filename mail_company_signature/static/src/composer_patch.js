import {Composer} from "@mail/core/common/composer";
import {isHtmlEmpty} from "@web/core/utils/html";
import {markup} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";

/**
 * The signature block shown under the composer, and inserted in the full
 * composer, is the one the server builds for this record
 * (``thread.mailCompanySignature``, loaded with the chatter data): the email
 * goes out with the same signature. Without it (other composers), the
 * user's stored signature.
 */
patch(Composer.prototype, {
  get signatureUser() {
    return this.thread?.effectiveSelf?.main_user_id;
  },
  get companySignature() {
    const recordSignature = this.thread?.mailCompanySignature;
    return recordSignature === undefined ? this.signatureUser?.signature : recordSignature;
  },
  get showSignaturePreview() {
    return Boolean(
      this.props.type === "message" &&
        !this.props.composer.message &&
        this.thread &&
        this.thread.model !== "discuss.channel" &&
        !isHtmlEmpty(this.companySignature)
    );
  },
  get signatureBlock() {
    if (this.thread?.mailCompanySignature === undefined) {
      return this.signatureUser?.getSignatureBlock() ?? "";
    }
    const signature = this.thread.mailCompanySignature;
    if (isHtmlEmpty(signature)) {
      return "";
    }
    const div = document.createElement("div");
    div.setAttribute("data-o-mail-quote", "1");
    const content = document.createElement("div");
    content.innerHTML = signature;
    div.append(document.createTextNode("-- "), document.createElement("br"), ...content.childNodes);
    return markup(div.outerHTML);
  },
  formatDefaultBodyForFullComposer(defaultBody, signature = "") {
    if (signature && this.thread?.mailCompanySignature !== undefined) {
      signature = this.signatureBlock;
    }
    return super.formatDefaultBodyForFullComposer(defaultBody, signature);
  },
  onClickRemoveSignature() {
    this.props.composer.emailAddSignature = false;
  },
  onClickRestoreSignature() {
    this.props.composer.emailAddSignature = true;
  },
});
