import logging
from lxml import etree
from odoo.tools import view_validation

_logger = logging.getLogger(__name__)

# Store original validators
_original_validators = {}


def _recursive_aware_validator(arch, **kwargs):
    """
    Validator that strips the 'recursive' attribute before delegating to original validators.
    This allows the recursive attribute to be used without triggering validation errors.
    """
    try:
        # Get the view type from the arch tag
        view_type = arch.tag
        
        # Deep copy the arch element to avoid mutating the original
        arch_copy = etree.fromstring(etree.tostring(arch))
        
        # Strip the 'recursive' attribute on the root if present
        if "recursive" in arch_copy.attrib:
            del arch_copy.attrib["recursive"]
        
        # Get original validators for this view type
        original_validators = _original_validators.get(view_type, [])
        
        # Run original validators against the sanitized copy
        for validator in original_validators:
            result = validator(arch_copy, **kwargs)
            if not result:
                return False
        return True
    except Exception as e:
        # Fail open: do not block view loading because of our wrapper
        _logger.exception("Recursive validation wrapper failed for %s view; skipping validation.", arch.tag)
        return True


def _patch_validators():
    """Patch the view validators to support the recursive attribute."""
    for view_type in ("list", "tree"):
        # Store original validators if not already stored
        if view_type not in _original_validators:
            _original_validators[view_type] = list(view_validation._validators.get(view_type, []))
        
        # Check if already patched
        current_validators = view_validation._validators.get(view_type, [])
        if current_validators and any(
            getattr(v, '__name__', '') == '_recursive_aware_validator' 
            for v in current_validators
        ):
            continue
        
        # Replace with our wrapper
        view_validation._validators[view_type] = [_recursive_aware_validator]


# Patch validators when module is imported
_patch_validators()
