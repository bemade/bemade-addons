# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Split a bilingual « French ⏎⏎ English » warning into its two halves.

Pure functions, no Odoo dependency. The detector is deliberately
conservative: a text is split only when its blank-line-separated blocks read
French first, then English, with a single switch, and both halves have a
comparable length (one is a translation of the other). Everything else is
left alone.
"""

import re

# Function words only: they say which language a sentence is in, whatever it
# is about. Words common to both languages ("on", "a", "client", "service"…)
# are left out on purpose.
FRENCH_WORDS = frozenset("""
    le la les un une des du de au aux et ou mais donc car ne pas plus
    que qu qui quoi dont où ce cet cette ces se sa son ses leur leurs nous
    vous ils elles est sont être été avoir ont doit doivent peut faut
    pour par avec sans sur sous dans chez avant après entre vers selon
    tout toute tous toutes aucun aucune chaque si lorsque quand afin
    jusqu en il elle ceci cela ça votre notre nos vos très aussi
    seulement uniquement veuillez assurer vérifier ajouter mettre
""".split())

ENGLISH_WORDS = frozenset("""
    the of and to in is are be been was were it its this that these those
    for with without from by at into onto about before after prior until
    any all each every no not only also must should shall will would can
    could may please do does did don doesn have has had if when then than
    our your their we you they he she them us there here which who what
    ensure make sure add verify check use require required
""".split())

FRENCH_LETTERS = set("éèêëàâäçùûüôöîïœæ")

WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
BLANK_LINE_RE = re.compile(r"\n[ \t]*\n+")

# A translation is rarely less than half or more than two and a half times
# as long as its source (French runs ~15-20% longer than English).
MIN_RATIO, MAX_RATIO = 0.5, 2.5


def _normalise(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _blocks(text):
    return [b.strip("\n") for b in BLANK_LINE_RE.split(text) if b.strip()]


def detect_language(block):
    """Return ``"fr"``, ``"en"`` or ``"?"`` for one block of text."""
    words = WORD_RE.findall(block.lower())
    fr = sum(1 for w in words if w in FRENCH_WORDS)
    fr += sum(1 for w in words if FRENCH_LETTERS.intersection(w))
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    total = fr + en
    if not total:
        return "?"
    if fr > en and fr / total >= 0.7:
        return "fr"
    if en > fr and en / total >= 0.7:
        return "en"
    return "?"


def analyse_bilingual(text):
    """Classify ``text`` and split it when it is « French ⏎⏎ English ».

    Returns ``(status, french, english)``; ``french``/``english`` are set
    only when ``status == "split"``. Other statuses:

    - ``empty``: no text;
    - ``single``: one block only, nothing to split;
    - ``monolingual``: several blocks, one language (or unclassified blocks);
    - ``reversed``: English first, then French — not split;
    - ``ambiguous``: unclassified block among both languages, several
      switches, or halves of too different lengths — not split.
    """
    if not text or not text.strip():
        return ("empty", None, None)
    blocks = _blocks(_normalise(text))
    if len(blocks) < 2:
        return ("single", None, None)
    labels = [detect_language(b) for b in blocks]
    if not ("fr" in labels and "en" in labels):
        return ("monolingual", None, None)
    if "?" in labels:
        return ("ambiguous", None, None)
    runs = [lang for i, lang in enumerate(labels) if i == 0 or labels[i - 1] != lang]
    if runs == ["en", "fr"]:
        return ("reversed", None, None)
    if runs != ["fr", "en"]:
        return ("ambiguous", None, None)
    switch = labels.index("en")
    french = "\n\n".join(blocks[:switch])
    english = "\n\n".join(blocks[switch:])
    if not MIN_RATIO <= len(french) / len(english) <= MAX_RATIO:
        return ("ambiguous", None, None)
    return ("split", french, english)


def split_bilingual(text):
    """Return ``(french, english)`` for a « French ⏎⏎ English » text, else None."""
    status, french, english = analyse_bilingual(text)
    return (french, english) if status == "split" else None
