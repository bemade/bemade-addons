from . import controllers
from . import models
from . import wizards
from .hooks import post_remove_old_module

# This module loads ``kubernetes``, whose ``kubernetes.client`` imports its
# pydantic models lazily. freezegun's ``freeze_time`` scans every loaded
# module's attributes, which triggers that import while ``datetime`` is
# already faked: pydantic cannot build a schema for ``FakeDatetime``, the
# freeze raises halfway through starting, and the clock stays frozen for the
# rest of the process. Every later test sees a stopped clock, and an HttpCase
# then waits forever for Chrome to exit. Keep freezegun out of kubernetes.
try:
    import freezegun
except ImportError:
    pass
else:
    freezegun.configure(extend_ignore_list=["kubernetes"])
