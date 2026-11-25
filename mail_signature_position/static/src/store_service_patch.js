import {Store} from "@mail/core/common/store_service";
import {patch} from "@web/core/utils/patch";

/** @type {import("models").Store} */
const storePatch = {
  setup() {
    super.setup(...arguments);
    /**
     * Current company's choice, sent by `res.users._init_store_data`.
     * @type {"below"|"above"}
     */
    this.mail_signature_position = "below";
  },
};
patch(Store.prototype, storePatch);
