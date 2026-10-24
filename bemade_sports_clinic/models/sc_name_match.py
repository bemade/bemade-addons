"""Task 1674 — the shared player-name matcher (pure Python, no ORM).

One place decides whether a typed first / last name designates an existing
player, for every player search of the app: the add-player existence check
(#1655), the header search (#1650), the Joueurs list search, and the backend
« Possible duplicates » review list.

Grades, best first:

* ``exact``  — same names once normalised (case, accents, hyphens,
  apostrophes and spaces ignored);
* ``prefix`` — every typed word starts a word of the name (#1650's rule);
* ``near``   — both names close enough, or the two names swapped:

  - Damerau–Levenshtein distance ≤ 1 for a name of ≤ 6 letters, ≤ 2 above
    (a transposition counts 1); names under 4 letters never match by
    distance (short names don't over-match);
  - the same French phonetic key (ph/f, qu/k/c, ç/s, eau/au/o, ai/ei/è,
    silent final e/s/t/x, double letters…), names of 3+ letters;
  - a compound name: one part of a hyphenated / multi-word name matches the
    other name (particles « de / du / des / le / la / st / saint » are
    optional);
  - first and last swapped (each matching the other exactly or near).

Speed: ``NameIndex`` keeps each candidate's normalised forms and keys once,
and ``near`` checks run only on candidates passing a cheap length window, so
~1,200 players stay well under the 150 ms target (measured by
tests/test_near_match_1674.py).
"""
import re
import unicodedata

PARTICLES = frozenset({'de', 'du', 'des', 'le', 'la', 'les', 'st', 'ste', 'saint', 'sainte', 'd', 'l'})
_SPLIT_RE = re.compile(r"[\s\-'’‘`´.]+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def fold(text):
    """Lower case, without accents (« Élodie » -> « elodie »)."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def words(text):
    """The typed words, folded (#1650's tokens)."""
    return _WORD_RE.findall(fold(text))


def parts(text):
    """The name's words, folded; « St » / « Ste » read « saint » / « sainte »."""
    out = []
    for part in _SPLIT_RE.split(fold(text)):
        part = "".join(_WORD_RE.findall(part))
        if not part:
            continue
        out.append({'st': 'saint', 'ste': 'sainte'}.get(part, part))
    return out


def compact(text):
    """The whole name as one token (« Synthé-Côté » -> « synthecote »)."""
    return "".join(parts(text))


def core(text):
    """``compact`` without the particles (« de la Fontaine » -> « fontaine »)."""
    words = [part for part in parts(text) if part not in PARTICLES]
    return "".join(words) or compact(text)


_PHONETIC_RULES = (
    (re.compile(r"ph"), "f"),
    (re.compile(r"(qu|q)"), "k"),
    (re.compile(r"c(?=[eiy])"), "s"),
    (re.compile(r"ck|c"), "k"),
    (re.compile(r"g(?=[eiy])"), "j"),
    (re.compile(r"gu(?=[eiy])"), "g"),
    (re.compile(r"eau|au"), "o"),
    (re.compile(r"ai|ei"), "e"),
    (re.compile(r"y"), "i"),
    (re.compile(r"z"), "s"),
    (re.compile(r"w"), "v"),
    (re.compile(r"(?<![cs])h"), ""),
)


def phonetic(text):
    """A rough French phonetic key of a name (accents already folded)."""
    raw = unicodedata.normalize("NFKD", str(text or "")).casefold().replace("ç", "s")
    key = "".join(parts(raw))
    if not key:
        return ""
    for pattern, repl in _PHONETIC_RULES:
        key = pattern.sub(repl, key)
    key = re.sub(r"(.)\1+", r"\1", key)
    # Silent final letters (« Thibault » / « Thibeau », « Gauthier » / « Gautier »).
    while len(key) > 3 and key[-1] in "estx":
        key = key[:-1]
    return key


def distance(a, b, limit=2):
    """Damerau–Levenshtein (optimal string alignment) distance between ``a``
    and ``b``, or ``limit + 1`` as soon as it exceeds ``limit``."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > limit:
        return limit + 1
    prev2 = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        best = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            value = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                value = min(value, prev2[j - 2] + 1)
            cur[j] = value
            best = min(best, value)
        if best > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[lb]


def allowed_distance(a, b):
    """The typo budget of a pair of names: none under 4 letters, 1 up to 6,
    2 above."""
    size = min(len(a), len(b))
    if size < 4:
        return 0
    return 1 if size <= 6 else 2


class NameForm:
    """A name's precomputed forms (built once per candidate / query)."""

    __slots__ = ('raw', 'parts', 'compact', 'core', 'phonetic', 'part_set')

    def __init__(self, text):
        self.raw = text or ''
        self.parts = parts(text)
        self.compact = "".join(self.parts)
        self.core = core(text)
        self.phonetic = phonetic(text)
        self.part_set = frozenset(p for p in self.parts if p not in PARTICLES and len(p) >= 3)


def name_equal(a, b):
    return bool(a.compact) and (a.compact == b.compact or a.core == b.core)


def name_near(a, b):
    """``a`` and ``b`` (NameForm) are the same name, typo'd, spoken alike, or
    one is a part of the other's compound name."""
    if not a.compact or not b.compact:
        return False
    if name_equal(a, b):
        return True
    budget = allowed_distance(a.core, b.core)
    if budget and distance(a.core, b.core, budget) <= budget:
        return True
    if min(len(a.core), len(b.core)) >= 3 and a.phonetic and a.phonetic == b.phonetic:
        return True
    # Compound names: a single name is one part of the other's compound
    # name (« Côté » / « Synthé-Côté »). Two different compounds sharing a
    # part (« Tremblay-Roy » / « Tremblay-Gagnon ») are NOT the same name.
    for one, other in ((a, b), (b, a)):
        if len(one.part_set) == 1 and len(other.part_set) > 1 and one.part_set <= other.part_set:
            return True
    return False


def prefix_match(query_words, *names):
    """#1650's rule: every typed word starts a word of the name."""
    tokens = [token for name in names for token in _WORD_RE.findall(fold(name))]
    return all(any(token.startswith(word) for token in tokens) for word in query_words)


def typed_prefix(first, last, cand_first, cand_last):
    """#1650's rule on a typed first + last name (NameForm), word for word
    as typed (no particle mapping)."""
    first_words = _WORD_RE.findall(fold(first.raw))
    last_words = _WORD_RE.findall(fold(last.raw))
    return bool(first_words and last_words) and prefix_match(first_words, cand_first.raw) \
        and prefix_match(last_words, cand_last.raw)


EXACT, PREFIX, NEAR = 'exact', 'prefix', 'near'
GRADE_ORDER = {EXACT: 0, PREFIX: 1, NEAR: 2}


def grade(first, last, cand_first, cand_last):
    """How the typed ``first`` / ``last`` (NameForm) designate a candidate
    (NameForm): EXACT, PREFIX, NEAR or None."""
    if name_equal(first, cand_first) and name_equal(last, cand_last):
        return EXACT
    query_words = list(first.parts) + list(last.parts)
    if typed_prefix(first, last, cand_first, cand_last):
        return PREFIX
    if not query_words:
        return None
    if name_near(first, cand_first) and name_near(last, cand_last):
        return NEAR
    if name_near(first, cand_last) and name_near(last, cand_first):
        return NEAR
    return None


def grade_words(words, cand_first, cand_last):
    """The one-box searches (header search, a free text): every typed word
    starts a word of the name (PREFIX), else every typed word of 3+ letters
    is near a part of the name (NEAR); None otherwise."""
    if not words:
        return None
    if prefix_match(words, cand_first.raw, cand_last.raw):
        return PREFIX
    if any(len(word) < 3 for word in words):
        return None
    targets = [NameForm(part) for part in cand_first.parts + cand_last.parts]
    targets += [cand_first, cand_last]
    for word in words:
        form = NameForm(word)
        if not any(name_near(form, target) for target in targets):
            return None
    return NEAR


class NameIndex:
    """Candidates ``[(id, first, last), ...]`` with their forms computed
    once; ``match(first, last)`` -> ``[(id, grade)]`` best grade first."""

    def __init__(self, rows):
        self.rows = [(rid, NameForm(first), NameForm(last)) for rid, first, last in rows]

    @staticmethod
    def _window(query, cand_first, cand_last):
        """Cheap pre-filter for the near grades: a length window on the
        names (either order)."""
        def close(a, b):
            return abs(len(a.core) - len(b.core)) <= 2 or a.part_set & b.part_set \
                or len(a.part_set) > 1 or len(b.part_set) > 1
        first, last = query
        return (close(first, cand_first) and close(last, cand_last)) or \
               (close(first, cand_last) and close(last, cand_first))

    def match(self, first, last):
        query = (NameForm(first), NameForm(last))
        out = []
        for rid, cand_first, cand_last in self.rows:
            if not self._window(query, cand_first, cand_last):
                # Prefix matches may still differ in length (« Ma » / « Martin »).
                if typed_prefix(query[0], query[1], cand_first, cand_last):
                    out.append((rid, PREFIX))
                continue
            found = grade(query[0], query[1], cand_first, cand_last)
            if found:
                out.append((rid, found))
        out.sort(key=lambda item: GRADE_ORDER[item[1]])
        return out

    def match_words(self, words):
        out = []
        for rid, cand_first, cand_last in self.rows:
            found = grade_words(words, cand_first, cand_last)
            if found:
                out.append((rid, found))
        out.sort(key=lambda item: GRADE_ORDER[item[1]])
        return out


def duplicate_pairs(rows):
    """The likely duplicate pairs among ``rows`` ``[(id, first, last, dob)]``:
    ``[(id_a, id_b, kind, same_dob)]`` with kind 'exact' (same normalised
    names), 'swapped' (first / last inverted) or 'near'. Candidates are
    compared within blocks (the last name's phonetic key, its first and last
    letters, the swapped pair), never all against all."""
    forms = {rid: (NameForm(first), NameForm(last), dob) for rid, first, last, dob in rows}
    blocks = {}

    def add(key, rid):
        if key[1]:
            blocks.setdefault(key, []).append(rid)

    for rid, (first, last, _dob) in forms.items():
        add(('ph', last.phonetic), rid)
        add(('l2', last.core[:2]), rid)
        add(('l3e', last.core[-3:]), rid)
        add(('sw', '|'.join(sorted((first.core, last.core)))), rid)
        for part in last.part_set:
            add(('part', part), rid)
    seen = set()
    out = []
    for ids in blocks.values():
        if len(ids) < 2:
            continue
        ids = sorted(set(ids))
        for i, a in enumerate(ids):
            fa, la, da = forms[a]
            for b in ids[i + 1:]:
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                fb, lb, db = forms[b]
                if not (fa.compact and la.compact and fb.compact and lb.compact):
                    continue
                if name_equal(fa, fb) and name_equal(la, lb):
                    kind = 'exact'
                elif name_equal(fa, lb) and name_equal(la, fb):
                    kind = 'swapped'
                elif (name_near(fa, fb) and name_near(la, lb)) or (name_near(fa, lb) and name_near(la, fb)):
                    kind = 'near'
                else:
                    continue
                out.append((a, b, kind, bool(da and db and da == db)))
    out.sort(key=lambda pair: (not pair[3], {'exact': 0, 'swapped': 1, 'near': 2}[pair[2]], pair[0], pair[1]))
    return out
