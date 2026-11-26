import {Thread} from "@mail/core/common/thread_model";
import {fields} from "@mail/model/misc";
import {patch} from "@web/core/utils/patch";

patch(Thread.prototype, {
  setup() {
    super.setup(...arguments);
    /** Current user's signature built for this record (server side). */
    this.mailCompanySignature = fields.Html(undefined);
  },
});
