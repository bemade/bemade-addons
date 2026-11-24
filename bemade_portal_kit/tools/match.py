# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the name matching of the search and the pickers.

The same rule as the kit's ``pk_match.js`` (the picker's type-to-filter):
case- and accent-insensitive, every typed word the start of a word of the
name (« ann ber » finds « Bérubé, Anne »).
"""
import re
import unicodedata

_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def pk_fold(text):
    """Lower case, without accents (« Élodie » -> « elodie »)."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def pk_words(text):
    """The folded words of ``text``."""
    return _WORD_RE.findall(pk_fold(text))


def pk_name_matches(query_words, *names):
    """Every typed word is the start of a word of the names."""
    tokens = [token for name in names for token in pk_words(name)]
    return all(any(token.startswith(word) for token in tokens) for word in query_words)
