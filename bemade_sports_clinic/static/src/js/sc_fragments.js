/*
 * bemade_portal_kit shim — task 5199 (P4a): the screen refresh moved to the
 * kit (@bemade_portal_kit/js/pk_fragments). This one-release alias keeps the
 * old module path working for code outside this addon; every importer here
 * uses the kit path. It goes in the next phase.
 */
export {
    applyFragments,
    FRAGMENTS_HEADER,
    flushFragments,
    markDirty,
    matchFragmentKeys,
    pageIsStale,
    patternToRegExp,
    requestRefresh,
    serverNow,
} from "@bemade_portal_kit/js/pk_fragments";
