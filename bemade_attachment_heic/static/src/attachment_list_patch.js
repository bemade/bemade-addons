import {AttachmentList} from "@mail/core/common/attachment_list";

import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

export const HEIC_MIMETYPES = [
  "image/heic",
  "image/heif",
  "image/heic-sequence",
  "image/heif-sequence",
];

/**
 * @param {import("models").Attachment} attachment
 * @returns {boolean}
 */
export function isHeicAttachment(attachment) {
  const name = (attachment.name || "").toLowerCase();
  return (
    HEIC_MIMETYPES.includes(attachment.mimetype) ||
    name.endsWith(".heic") ||
    name.endsWith(".heif")
  );
}

patch(AttachmentList.prototype, {
  setup() {
    super.setup(...arguments);
    this.heicOrm = useService("orm");
    this.heicNotification = useService("notification");
    this.heicStore = useService("mail.store");
  },

  /**
   * @param {import("models").Attachment} attachment
   */
  canConvertHeic(attachment) {
    return (
      !this.env.inComposer &&
      !attachment.uploading &&
      attachment.type !== "url" &&
      attachment.id > 0 &&
      this.heicStore.self?.main_user_id?.share === false &&
      isHeicAttachment(attachment)
    );
  },

  /**
   * @param {import("models").Attachment} attachment
   */
  async onClickConvertHeic(attachment) {
    let data = null;
    try {
      data = await this.heicOrm.call("ir.attachment", "action_convert_heic_to_jpeg", [
        [attachment.id],
      ]);
    } catch (error) {
      const message = error?.data?.message;
      if (error?.data?.name === "odoo.exceptions.UserError" && message) {
        this.heicNotification.add(message, {type: "danger", sticky: true});
        return;
      }
      throw error;
    }
    this.heicStore.insert(data);
    this.heicNotification.add(_t("The photo was converted to JPEG."), {
      type: "success",
    });
  },

  getActions(attachment) {
    const actions = super.getActions(attachment);
    if (this.canConvertHeic(attachment)) {
      actions.push({
        label: _t("Convert to JPEG"),
        icon: "fa fa-file-image-o",
        onSelect: () => this.onClickConvertHeic(attachment),
      });
    }
    return actions;
  },
});
