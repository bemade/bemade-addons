# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The installable app's templates, adopted from the first consumer.

Task 5201 (kit P6): the install page and the offline page were the first
consumer's templates. Their ``ir.ui.view`` records keep their ids (their
translations and any inheriting view stay); only the external id and key
move to this addon (``bemade_portal_kit.tools.adopt.adopt_views`` with
``target``). The old module and names below are historical data, the one
place this addon names the first consumer.

Entry points: this addon's ``pre_init_hook`` (it is installed as a new
dependency of the consumer's upgrade) and the consumer's own pre-migration
(idempotent; a no-op once adopted).
"""
PWA = 'bemade_portal_kit_pwa'

# (old module, old name, new name)
PWA_ADOPTED_VIEWS = (
    ('bemade_sports_clinic', 'sc_app_install', 'pk_app_install'),
    ('bemade_sports_clinic', 'sc_app_offline', 'pk_app_offline'),
)
