#    Bemade Inc.
#
#    Copyright (C) 2024-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Fix videocall_location href in calendar email templates."""
    _logger.info("Fixing calendar email template videocall_location hrefs...")

    replacements = [
        (
            "object.event_id.videocall_location",
            "{{object.event_id.videocall_location}}",
        ),
        ("object.videocall_location", "{{object.videocall_location}}"),
    ]

    fixed_templates = env["mail.template"]
    for problem_string, replacement in replacements:
        fixed_templates |= _replace_problem_string(env, problem_string, replacement)

    # Commit the changes since we're in a post_init_hook
    env.cr.commit()
    _logger.info("Committed calendar template fixes to database")


def _replace_problem_string(env, problem_string, replacement):
    """Find and fix broken t-attf-href attributes in mail templates."""

    def wrap(string) -> str:
        return f't-attf-href="{string}"'

    search_pattern = wrap(problem_string)

    # Search for templates containing the broken href
    problem_templates = env["mail.template"].search(
        [("body_html", "ilike", search_pattern)]
    )

    for template in problem_templates:
        # Convert Markup to string for replace to work
        old_html_str = str(template.body_html) if template.body_html else ""
        new_html = old_html_str.replace(wrap(problem_string), wrap(replacement))

        if old_html_str != new_html:
            template.write({"body_html": new_html})
            _logger.info(f"Fixed template: {template.name}")

    return problem_templates
