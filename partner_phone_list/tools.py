# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Pure helpers shared by the models and the install seed."""

import re

from odoo.exceptions import UserError

from odoo.addons.phone_validation.tools import phone_validation

# A trailing extension: "x12", "ext 12", "ext. 12", "extension 12",
# "poste 12", "#12" (optionally preceded by a comma or a semicolon).
EXTENSION_RE = re.compile(
    r"""\s*[,;]?\s*
        (?:(?<![a-z])(?:extension|ext|poste|post)\.?|(?<![a-z])x|\#)
        \s*[:.]?\s*(\d{1,6})\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def digits(value):
    return re.sub(r"\D", "", str(value) if value else "")


def split_extension(value):
    """Return ``(number, extension)`` for a phone string; ``extension`` is
    False when the value does not end with a recognised extension."""
    value = (str(value) if value else "").strip()
    match = EXTENSION_RE.search(value)
    if match:
        number = value[: match.start()].strip(" ,;-")
        if len(digits(number)) >= 4:
            return number, match.group(1)
    return value, False


def sanitize(number, country_code, phone_code):
    """E.164 form of ``number`` for the given country, or False when the
    number cannot be parsed (same rule as phone_validation's ``_phone_format``).
    """
    if not number:
        return False
    try:
        return phone_validation.phone_format(
            number, country_code, phone_code, force_format="E164", raise_exception=True
        )
    except UserError:
        return False


def format_number(number, country_code, phone_code):
    """International form of ``number`` (phone_validation, like the standard
    Phone field), or the value as typed (trimmed) when it does not parse or
    when parsing would drop or change digits: the parser ignores trailing
    text, so "514-555-0101, 456" must not become "+1 514-555-0101"."""
    if not number:
        return number
    number = number.strip()
    try:
        formatted = phone_validation.phone_format(
            number, country_code, phone_code, force_format="INTERNATIONAL", raise_exception=True
        )
    except UserError:
        return number
    # an extension found by the parser (", 456") belongs in its own column
    if not formatted or " ext. " in formatted or not same_digits(formatted, number):
        return number
    return formatted


def number_key(number, extension, country_code, phone_code):
    """Matching key of a number: ``(sanitized or digits, extension, parsed)``."""
    sanitized = sanitize(number, country_code, phone_code)
    return (sanitized or digits(number), (extension or "").strip(), bool(sanitized))


def same_digits(a, b):
    """True when two spellings of a number carry the same digits, allowing
    for a country / trunk prefix on one side (514... vs 1514... vs 001514...).
    Guards matches on the E.164 form, which the parser obtains by ignoring
    trailing text (e.g. "514-555-0101, 123" and "514-555-0101, 456")."""
    da, db = digits(a), digits(b)
    if da == db:
        return True
    return bool(da and db) and (da.endswith(db) or db.endswith(da))
