"""Find and remove user signatures that a mail template printed in its body."""

import re

from lxml import etree, html
from markupsafe import Markup

DASHES = "--"


def text_key(content):
    """Text of an HTML fragment with every whitespace removed (comparison key)."""
    if not content:
        return ""
    try:
        text = html.fragment_fromstring(str(content), create_parent="div").text_content()
    except (etree.ParserError, ValueError):
        text = str(content)
    return re.sub(r"\s+", "", text)


def _node_key(element):
    return re.sub(r"\s+", "", element.text_content())


def _tail_key(element):
    return re.sub(r"\s+", "", element.tail or "")


def _targets(signatures):
    """Comparison keys of the signatures to remove.

    ``signatures`` is a list of ``(signature_html, plain_name)``. A signature
    whose text is only the user's name (Odoo's default signature) is matched only
    when it follows the ``--`` separator: a bare name elsewhere in a template is
    not a signature.
    """
    targets = set()
    for signature, name in signatures:
        key = text_key(signature)
        if len(key) < 3:
            continue
        targets.add(DASHES + key)
        if key != text_key(name):
            targets.add(key)
    return targets


def _drop_run(run):
    for element in run[:-1]:
        element.tail = None
    for element in run:
        element.drop_tree()


def _strip(parent, targets, longest):
    """Remove, under ``parent``, the outermost element (or run of sibling
    elements) whose text is one of ``targets``. Returns the number removed."""
    removed = 0
    for child in list(parent):
        if not isinstance(child.tag, str):
            continue  # comment, processing instruction
        key = _node_key(child)
        if key in targets:
            child.drop_tree()
            removed += 1
        elif any(target in key for target in targets):
            removed += _strip(child, targets, longest)
    # Runs of sibling elements (a signature printed without a wrapper).
    children = [child for child in parent if isinstance(child.tag, str)]
    start = 0
    while start < len(children):
        accumulated = ""
        matched = False
        for end in range(start, len(children)):
            accumulated += _node_key(children[end])
            if accumulated in targets and end > start:
                _drop_run(children[start : end + 1])
                removed += 1
                start = end + 1
                matched = True
                break
            accumulated += _tail_key(children[end])
            if len(accumulated) > longest or not any(
                target.startswith(accumulated) for target in targets
            ):
                break
        if not matched:
            start += 1
    return removed


def strip_printed_signatures(body, signatures):
    """Return ``body`` without the user signatures a template printed.

    :param body: rendered template body (HTML)
    :param signatures: list of ``(signature_html, user_name)``
    :rtype: Markup
    """
    targets = _targets(signatures)
    if not body or not targets:
        return body
    try:
        root = html.fragment_fromstring(str(body), create_parent="div")
    except (etree.ParserError, ValueError):
        return body
    if not _strip(root, targets, max(len(target) for target in targets)):
        return body
    content = (root.text or "") + "".join(
        etree.tostring(child, encoding="unicode", method="html") for child in root
    )
    return Markup(content)
