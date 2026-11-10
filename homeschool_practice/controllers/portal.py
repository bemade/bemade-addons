# -*- coding: utf-8 -*-
import json

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request


class PracticePortal(http.Controller):

    @http.route("/my/homeschool/practice", type="http", auth="user", website=False)
    def practice(self, **kw):
        student = request.env["homeschool.student"].sudo().search([("user_id", "=", request.env.uid)], limit=1)
        if not student or request.env.user._is_internal():
            raise Forbidden()
        html = request.env["ir.qweb"]._render("homeschool_practice.practice_app", {
            "student": student, "lang": (request.env.user.lang or "fr_CA").replace("_", "-"),
            "asset_version": request.env["ir.module.module"].sudo().search(
                [("name", "=", "homeschool_practice")], limit=1).latest_version or "1",
        })
        return request.make_response("<!DOCTYPE html>\n" + str(html), headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/my/homeschool/practice/manifest.webmanifest", type="http", auth="public")
    def manifest(self):
        body = {
            "name": "Pratique", "short_name": "Pratique", "start_url": "/my/homeschool/practice",
            "scope": "/my/homeschool/practice", "display": "standalone", "orientation": "landscape",
            "background_color": "#14213d", "theme_color": "#14213d",
            "icons": [{"src": "/homeschool_practice/static/src/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "/homeschool_practice/static/src/img/icon-512.png", "sizes": "512x512", "type": "image/png"}],
        }
        return request.make_response(json.dumps(body), headers=[("Content-Type", "application/manifest+json")])
