/*
 * Task 5516 — Discuss's « start a conversation » palette also lists the
 * PORTAL users for an internal user (the core keeps to internal users on
 * the client too: ``partner.main_user_id?.share === false``). The server
 * search already returns them (res.partner._search_for_channel_invite).
 *
 * Kept tiny (upgrade-fragile): after the core's results, the matching
 * portal partners fill the remaining places.
 */
import { DiscussCommandPalette } from "@mail/discuss/core/public_web/discuss_command_palette";
import { cleanTerm } from "@mail/utils/common/format";
import { patch } from "@web/core/utils/patch";

import { pkPortalPartners } from "@bemade_portal_kit_chat/backend/pk_chat_portal_partners";

patch(DiscussCommandPalette.prototype, {
    buildResults(filtered) {
        super.buildResults(...arguments);
        if (!this.store.self_partner || this.store.self_partner.main_user_id?.share !== false) {
            return;
        }
        const limit = (this.ui.isSmall ? 7 : 10) - this.commands.length - (filtered ? filtered.size : 0);
        const shown = new Set(filtered || []);
        const extra = pkPortalPartners(
            Object.values(this.store["res.partner"].records),
            this.cleanedTerm,
            shown,
            limit,
            cleanTerm
        );
        for (const partner of extra) {
            this.commands.push(this.makeDiscussCommand(partner));
        }
    },
});
