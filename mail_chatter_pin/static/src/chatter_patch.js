import {Chatter} from "@mail/chatter/web_portal/chatter";
import {ChatterPinnedBlock} from "./chatter_pinned_block";
import {patch} from "@web/core/utils/patch";

Object.assign(Chatter.components, {ChatterPinnedBlock});

patch(Chatter.prototype, {
  get requestList() {
    return [...super.requestList, "pinnedMessages"];
  },
});
