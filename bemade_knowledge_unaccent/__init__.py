from . import models


def _uninstall_hook(env):
    env["knowledge.article"]._bemade_unaccent_body_search(enable=False)
