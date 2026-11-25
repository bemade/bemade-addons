# -*- coding: utf-8 -*-
import hashlib
import os

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

from odoo.addons.homeschool_portal.models.portal_kit import HS_APP


_STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "src")
_asset_version = None


def asset_version():
    """Hash of the lesson script and stylesheet, so a code change reaches a home-screen iPad without a version bump."""
    global _asset_version
    if _asset_version is None:
        digest = hashlib.sha1()
        for name in ("js/practice.js", "css/practice.css"):
            with open(os.path.join(_STATIC, name), "rb") as f:
                digest.update(f.read())
        _asset_version = digest.hexdigest()[:12]
    return _asset_version


class PracticePortal(http.Controller):

    @http.route("/my/homeschool/practice", type="http", auth="user", website=False)
    def practice(self, **kw):
        """The game, full screen (its own page: no portal or app chrome). Its ✕ goes
        back to the portal app's « Today » while the app is on for the learner, else
        to the stock homeschool page. The installed app is the portal kit's
        (``/my/app.webmanifest``): this page declares no manifest of its own."""
        student = request.env["homeschool.student"].sudo().search([("user_id", "=", request.env.uid)], limit=1)
        if not student or request.env.user._is_internal():
            raise Forbidden()
        kit = request.env["portal.kit"]
        in_app = kit._pk_shell_active() and kit._pk_current_app() == HS_APP
        exit_url = "/my/home" if in_app else "/my/homeschool"
        html = request.env["ir.qweb"]._render("homeschool_practice.practice_app", {
            "student": student, "lang": (request.env.user.lang or "fr_CA").replace("_", "-"),
            "asset_version": asset_version(), "exit_url": exit_url,
        })
        return request.make_response("<!DOCTYPE html>\n" + str(html), headers=[("Content-Type", "text/html; charset=utf-8")])
