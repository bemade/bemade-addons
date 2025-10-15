from . import models
from . import validation


def pre_init_hook(env):
    """Ensure validation patching happens before any views are loaded."""
    from . import validation
    validation._patch_validators()
