# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers for ``portal.kit`` hooks. Synthetic content only.

``pk_hook(env, hook, build)`` swaps a ``portal.kit._pk_*()`` hook for the
duration of a ``with`` block: ``build(original)`` receives the result of the
installed chain (every consumer's ``super()``) and returns the content the
hook answers instead. Pass ``lambda _orig: {...}`` to REPLACE the content
(the kit tests do: the engine is tested on synthetic roles / nav / pages,
whatever consumer is installed), or extend ``_orig`` to ADD an entry (the
consumers' tests do). The per-registry cache is cleared on enter and exit.
"""
from contextlib import contextmanager, ExitStack
from unittest.mock import patch


@contextmanager
def pk_hook(env, hook, build):
    cls = type(env['portal.kit'])
    original = getattr(cls, hook)

    def patched(self):
        return build(original(self))

    env.registry.clear_cache()
    try:
        with patch.object(cls, hook, patched):
            yield
    finally:
        env.registry.clear_cache()


@contextmanager
def pk_hooks(env, **builds):
    """Several ``pk_hook`` at once: ``pk_hooks(env, _pk_nav=..., _pk_roles=...)``."""
    with ExitStack() as stack:
        for hook, build in builds.items():
            stack.enter_context(pk_hook(env, hook, build))
        yield


@contextmanager
def pk_extra_roles(env, func):
    """Swap ``res.users._pk_extra_roles`` (per-user, never cached)."""
    with patch.object(type(env['res.users']), '_pk_extra_roles', func):
        yield
