from odoo.tests import TransactionCase, tagged

JS_URL = "/web_m2x_narrow_inline_search/static/src/js/many2x_narrow_inline_search.js"
XML_URL = "/web_m2x_narrow_inline_search/static/src/xml/many2x_narrow_inline_search.xml"


@tagged("post_install", "-at_install")
class TestNarrowInlineSearchAssets(TransactionCase):
    """Assets-only module: verify both patch files land in the backend bundle and
    that the OWL template extension compiles against its core parent.

    The behavioural assertions (inline autocomplete on narrow non-touch windows,
    touch-only dialog input, list-first dialog) live in the hoot suite
    (``static/tests/many2x_narrow_inline_search.test.js``), which runs in the
    browser test job. These Python checks are the local install/integration smoke.
    """

    def _backend_bundle(self):
        return self.env["ir.qweb"]._get_asset_bundle("web.assets_backend")

    def test_backend_bundle_includes_module_assets(self):
        bundle = self._backend_bundle()
        js_urls = [asset.url for asset in bundle.javascripts]
        xml_urls = [asset.url for asset in bundle.templates]
        self.assertIn(JS_URL, js_urls, "JS patch must be bundled into web.assets_backend")
        self.assertIn(
            XML_URL, xml_urls, "Template extension must be bundled into web.assets_backend"
        )

    def test_template_extension_compiles_against_core_parent(self):
        # generate_xml_bundle() parses every OWL template, resolves t-inherit
        # parents and emits the registerTemplate/registerTemplateExtension codegen.
        # A malformed xpath or a missing parent would raise here or trip the
        # missing-parent guard, so this is a real compile check — not just a
        # substring probe.
        xml_bundle = self._backend_bundle().generate_xml_bundle()

        self.assertIn(
            'registerTemplateExtension("web.Many2XAutocomplete"',
            xml_bundle,
            "Our extension of web.Many2XAutocomplete must be registered",
        )
        self.assertIn(
            "useMobileSearchInput",
            xml_bundle,
            "The xpath must rewrite the search-input t-if to the new getter",
        )
        # Core's web.Many2XAutocomplete lives in the same bundle, so the extension
        # parent is always resolvable — no missing-parent console.error emitted.
        self.assertNotIn("Missing (extension) parent templates", xml_bundle)
