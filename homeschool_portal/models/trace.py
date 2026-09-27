# -*- coding: utf-8 -*-
from odoo import models


class Trace(models.Model):
    """The outside teacher comments a trace from the portal chatter. ``mail`` requires
    ``_mail_post_access`` on the document to accept a post, and it defaults to ``write``:
    portal users only ever read traces (record rules of ``homeschool``), so a comment
    would be refused. Posting needs read access only. Core follow-up: move this line
    into ``homeschool.trace`` itself."""
    _inherit = "homeschool.trace"

    _mail_post_access = "read"
