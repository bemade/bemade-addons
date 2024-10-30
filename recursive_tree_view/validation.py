import logging
import os
from lxml import etree
from odoo.tools import misc, view_validation

_logger = logging.getLogger(__name__)

_tree_validator = None
RNG_NS = "http://relaxng.org/ns/structure/1.0"


def schema_tree(arch, **kwargs):
    global _tree_validator

    if _tree_validator is None:
        try:
            # Load and parse the existing schema file
            schema_path = os.path.join("addons", "base", "rng", "tree_view.rng")
            with misc.file_open(schema_path) as f:
                rng_doc = etree.parse(f)

            # Find the `tree` definition in the parsed document
            tree_define = rng_doc.find(".//{%s}define[@name='tree']" % RNG_NS)
            if tree_define is not None:
                # Add the `recursive` attribute as an optional attribute in the `tree` definition
                tree_elem = tree_define.find(".//{%s}element[@name='tree']" % RNG_NS)
                if tree_elem is not None:
                    optional_attr = etree.SubElement(
                        tree_elem,
                        _tag="{%s}optional" % RNG_NS,
                    )
                    recursive_attr = etree.SubElement(
                        optional_attr,
                        _tag="{%s}attribute" % RNG_NS,
                        name="recursive",
                    )

            # Create RelaxNG validator from the modified schema
            _tree_validator = etree.RelaxNG(rng_doc)

        except (etree.RelaxNGParseError, etree.XMLSyntaxError) as e:
            _logger.error("Error parsing RelaxNG schema: %s", e.error_log)
            return False
        except Exception as e:
            _logger.error("General error loading RelaxNG schema: %s", e)
            return False

    # Validate the XML arch
    if _tree_validator.validate(arch):
        return True

    # Log validation errors
    for error in _tree_validator.error_log:
        _logger.error("Validation error: %s", error)
    return False


# Register the validator with Odoo's view validation
view_validation._validators.update(tree=[schema_tree])
