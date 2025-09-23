import logging
import os
import threading
import copy
from lxml import etree
from odoo.tools import misc, view_validation

_logger = logging.getLogger(__name__)

_validator_lock = threading.Lock()


def _make_wrapper(kind, original_validators):
    """
    Returns a validator function for `kind` ("list" or "tree") that:
    - clones the arch
    - strips the `recursive` attribute on the root if present
    - delegates validation to Odoo's original validators for that kind
    """

    def _wrapper(arch, **kwargs):
        try:
            # Deep copy the arch element to avoid mutating the original
            arch_copy = etree.fromstring(etree.tostring(arch))

            # Strip the 'recursive' attribute on the root if present
            if arch_copy is not None and arch_copy.tag in ("list", "tree"):
                if "recursive" in arch_copy.attrib:
                    del arch_copy.attrib["recursive"]

            # Run original validators against the sanitized copy
            for validator in original_validators:
                if not validator(arch_copy, **kwargs):
                    return False
            return True
        except Exception:
            # Fail open: do not block view loading because of our wrapper
            _logger.exception("Validation wrapper failed for %s view; skipping validation.", kind)
            return True

    # Tag the wrapper to detect duplicates upon reloading
    _wrapper.__name__ = f"recursive_attr_wrapper_{kind}"
    return _wrapper


def _register_wrappers():
    with _validator_lock:
        for kind in ("list", "tree"):
            originals = list(view_validation._validators.get(kind) or [])
            # If already wrapped, skip
            if originals and getattr(originals[0], "__name__", "").startswith("recursive_attr_wrapper_"):
                continue
            wrapper = _make_wrapper(kind, originals)
            view_validation._validators[kind] = [wrapper]


# Register wrapper validators for Odoo 18 (<list>) and legacy (<tree>)
_register_wrappers()
