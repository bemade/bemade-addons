/*
 * Task 5516 — the palette's portal partners (pure, no import: the hoot
 * test and the palette patch share it).
 */

/**
 * The portal partners of ``partners`` whose cleaned name (``clean``)
 * includes ``term``, not already ``shown``, at most ``limit``.
 */
export function pkPortalPartners(partners, term, shown, limit, clean = (text) => text.toLowerCase()) {
    if (limit <= 0) {
        return [];
    }
    return partners
        .filter(
            (partner) =>
                partner.main_user_id?.share === true &&
                clean(partner.displayName || "").includes(term) &&
                !shown.has(partner)
        )
        .slice(0, limit);
}
