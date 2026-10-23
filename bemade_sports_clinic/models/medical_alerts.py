"""Task 1630 — allergies and medical alerts: levels, EpiPen, the legacy text.

The player's free-text ``allergies`` field is replaced by:

* ``allergy_level`` + ``allergy_details`` + ``allergy_epipen``;
* ``medical_alert_level`` + ``medical_alert_details`` (conditions);
* ``medical_history_other`` (therapists only, the Infos tab);
* ``medical_alert_review`` (« À valider »: pre-filled from the legacy text,
  to be validated by the clinic from the back-end list).

Levels: ``none`` (« Aucune », grey), ``minor`` (« Non urgente », yellow),
``urgent`` (« Urgente – risque vital », red); no value = « Non renseigné ».

This module holds the pure classification of a legacy ``allergies`` text
(the 19.0.1.99.0 post-migrate and the tests use it). Owner + MC decisions
2026-10-21:

* « aucune » and its variants -> allergy level « Aucune », details empty
  (matched case-, space-, punctuation- and accent-insensitively);
* empty -> nothing set (« Non renseigné »);
* real text -> pre-filled and flagged « à valider »: condition words ->
  medical alert; allergy words or no condition word -> allergies (a text with
  both fills both); « EpiPen » or « sévère / severe » -> urgent (the EpiPen
  box ticked when EpiPen is mentioned, never for « no / pas d'EpiPen »),
  otherwise not urgent. The original text is kept verbatim in the details.

Keyword lists live here, in code — never ids, never real player text (this
repository is public).
"""
import re
import unicodedata

LEVEL_NONE = 'none'
LEVEL_MINOR = 'minor'
LEVEL_URGENT = 'urgent'
LEVELS = (LEVEL_NONE, LEVEL_MINOR, LEVEL_URGENT)
# Most severe last; « not specified » (False) below « none ».
LEVEL_RANK = {False: 0, None: 0, '': 0, LEVEL_NONE: 1, LEVEL_MINOR: 2, LEVEL_URGENT: 3}

# Pill tones (sc_components.scss): unset = muted outline, none = grey.
LEVEL_TONES = {LEVEL_NONE: 'none', LEVEL_MINOR: 'minor', LEVEL_URGENT: 'urgent'}
UNSET_TONE = 'unset'
# What a coach sees (owner + MC 2026-10-21): yellow and red only.
COACH_LEVELS = (LEVEL_MINOR, LEVEL_URGENT)


def fold(text):
    """Lower-case, accents removed, whitespace collapsed."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('’', "'").replace(' ', ' ')
    return ' '.join(text.lower().split())


def squash(text):
    """``fold`` without any space or punctuation (« N/A » -> « na »,
    « Pas d'allergies. » -> « pasdallergies »)."""
    return re.sub(r'[\W_]+', '', fold(text))


# « aucune » and its variants, on the squashed text: a « no » word, then
# optionally « known », « drug / médicamenteuse », « allergie(s) », « or
# intolerances », « connue(s) », « reported / on file / au dossier », « à ce
# jour » — in that order (« Aucune allergie connue », « No known drug
# allergies reported », « No allergies or intolerances on file »).
_NONE_RE = re.compile(
    r'^(?:aucune?s?|none|no|non|nil|rien|neant|na|nka|nkda|nkfa|pasd|pasde|pas|sans)'
    r'(?:known)?'
    r'(?:drugs?|medicamenteuses?|alimentaires?)?'
    r'(?:allergies?|allergys?|alergies?|allergiques?)?'
    r'(?:medicamenteuses?|alimentaires?)?'
    r'(?:orintolerances?|ouintolerances?)?'
    r'(?:connues?|known)?'
    r'(?:reported|onfile|audossier|signalees?|declarees?|rapportees?)?'
    r'(?:acejour|todate)?$'
)

# Condition words (stems, on the folded text) -> the medical alert.
CONDITION_STEMS = (
    'asthm', 'diabet', 'insulin', 'epilep', 'convuls', 'seizure', 'crise d',
    'cardia', 'cardiaque', 'coeur', 'heart', 'arythm', 'arrhythm', 'souffle',
    'hemophil', 'drepanocyt', 'sickle', 'hypertens', 'hypotens', 'migrain',
    'commotion', 'concussion', 'inhalat', 'inhaler', 'ventolin', 'pompe',
    'anemi', 'thyroid', 'crohn', 'celiaqu', 'coeliaqu', 'celiac',
    # Owner review 2026-10-21 (prod values check): immunosuppression,
    # splenectomy, G6PD deficiency, a hemophilia factor product.
    'immuno', 'splenect', 'g6pd', 'wilat',
)
# Allergy words (stems, on the folded text) -> the allergies (a text with no
# condition word goes there too).
ALLERGY_STEMS = (
    'allerg', 'alerg', 'anaphyla', 'epipen', 'epi pen', 'epi-pen', 'arachide',
    'peanut', 'noix', ' nut', 'lactose', 'gluten', 'penicil', 'amoxicil',
    'sulfa', 'latex', 'fruits de mer', 'seafood', 'shellfish', 'crustace',
    'poisson', 'fish', 'oeuf', 'egg', 'abeille', 'guepe', 'bee', 'wasp',
    'piqure', 'sting', 'pollen', 'soya', 'sesame', 'kiwi', 'fraise',
    'intoleran', 'medicament', 'antibiot',
)

_EPIPEN = r'(?:epi\s*-?\s*pens?|auto-?\s*injecteur)'
EPIPEN_RE = re.compile(_EPIPEN)
# « no / pas d' / sans / aucun EpiPen » — a mention that is NOT a yes.
EPIPEN_NEGATIVE_RE = re.compile(
    r"(?:\bno\b|\bnot\b|\bpas\s+(?:d'|de\s+|d\s+|besoin\s+(?:d'|de\s+))?|\bsans\s+|\baucun\s+|\bwithout\s+|\bnon\s+)"
    r'\s*(?:an?\s+|un\s+|une\s+)?' + _EPIPEN)
SEVERE_RE = re.compile(r'\bsev[eè]re?s?\b|\bsevere(?:ly)?\b|\bsevere\b')


# Owner review 2026-10-21: the « --- Merged from … --- » provenance headers
# the merge wizard writes are not content.
_MERGE_HEADER_RE = re.compile(r'^\s*-{2,}\s*merged from\b.*$', re.IGNORECASE | re.MULTILINE)


def strip_merge_headers(text):
    return _MERGE_HEADER_RE.sub('', text or '')


def is_none_variant(text):
    """« aucune », « Aucune allergie connue », « N/A », « NKA »… and (owner
    review 2026-10-21) a text of only dashes / punctuation (« - ») or « x »."""
    text = strip_merge_headers(text)
    if (text or '').strip() and not squash(text):
        return True
    key = squash(text)
    return bool(key) and (key in ('x', 'xx', 'xxx') or bool(_NONE_RE.match(key)))


def _has_stem(folded, stems):
    padded = ' %s ' % folded
    return any(stem in padded for stem in stems)


def epipen_mentioned(folded):
    """True when EpiPen is mentioned positively at least once (each « no /
    pas d'EpiPen » mention is removed first)."""
    stripped = EPIPEN_NEGATIVE_RE.sub(' ', folded)
    return bool(EPIPEN_RE.search(stripped))


def classify_legacy_allergies(text):
    """The new fields for ONE legacy ``allergies`` text, as a dict, plus a
    ``kind`` key (not a field): ``'empty'``, ``'none'`` or ``'prefilled'``.

    ``text`` is kept verbatim in the details of a pre-filled entry."""
    raw = text or ''
    content = strip_merge_headers(raw)
    folded = fold(content)
    if not content.strip():
        return {'kind': 'empty'}
    if is_none_variant(content):
        # Owner review 2026-10-21: « aucune » means nothing to report on
        # both the allergies and the medical alert.
        return {'kind': 'none', 'allergy_level': LEVEL_NONE, 'allergy_details': False,
                'medical_alert_level': LEVEL_NONE, 'medical_alert_details': False}
    epipen = epipen_mentioned(folded)
    severe = bool(SEVERE_RE.search(folded))
    condition = _has_stem(folded, CONDITION_STEMS)
    allergy = _has_stem(folded, ALLERGY_STEMS) or epipen or not condition
    vals = {'kind': 'prefilled', 'medical_alert_review': True}
    if allergy:
        vals.update({
            'allergy_level': LEVEL_URGENT if (epipen or severe) else LEVEL_MINOR,
            'allergy_details': raw,
            'allergy_epipen': epipen,
        })
    if condition:
        vals.update({
            'medical_alert_level': LEVEL_URGENT if severe else LEVEL_MINOR,
            'medical_alert_details': raw,
        })
    return vals


def more_severe(*levels):
    """The most severe of ``levels`` (« not specified » loses to anything)."""
    best = False
    for level in levels:
        if LEVEL_RANK.get(level or False, 0) > LEVEL_RANK.get(best, 0):
            best = level
    return best
