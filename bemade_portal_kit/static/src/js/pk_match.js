/*
 * Task 5200 (kit P5) — the shell's name matching, shared by the picker
 * (pk_picker.js) and the header search (pk_search.js); the server side is
 * tools/match.py (pk_fold, pk_words, pk_name_matches), the same rule.
 *
 * Accent- and case-insensitive; every typed word must START a word of the
 * label (« ann tre » matches « Tremblay, Anne »).
 */

/** Lower case, without accents (« Élodie » -> « elodie »). */
export function pkFold(text) {
    return String(text || "")
        .normalize("NFKD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase();
}

/** The folded words of ``text`` (letters, digits, underscore). */
export function pkWords(text) {
    return pkFold(text).match(/[\p{L}\p{N}_]+/gu) || [];
}

/** Every word of ``queryWords`` starts a word of ``label``. */
export function pkNameMatches(queryWords, label) {
    const tokens = pkWords(label);
    return queryWords.every((word) => tokens.some((token) => token.startsWith(word)));
}
