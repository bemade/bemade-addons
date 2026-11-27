import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";

patch(Chatter.prototype, {
  get requestList() {
    return [...super.requestList, "mail_company_signature"];
  },
});
