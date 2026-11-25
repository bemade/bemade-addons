"""Minimal JSON-schema checker (no external dependency).

Supports the subset used to describe LLM answers: ``type`` (a name or a list
of names, incl. ``null``), ``properties``, ``required``,
``additionalProperties`` (boolean), ``enum``, ``minLength`` / ``maxLength``,
``items``, ``minimum`` / ``maximum``. Unknown keywords are ignored.
"""


class SchemaError(ValueError):
    pass


def _is_type(value, name):
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return True


def validate(value, schema, path="$"):
    """Raise ``SchemaError`` when ``value`` does not follow ``schema``."""
    if not isinstance(schema, dict):
        return
    expected = schema.get("type")
    if expected:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, name) for name in names):
            raise SchemaError(f"{path}: expected {'/'.join(names)}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: value not in enum")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError(f"{path}: longer than {schema['maxLength']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError(f"{path}: shorter than {schema['minLength']}")
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: above {schema['maximum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise SchemaError(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise SchemaError(f"{path}: unexpected {', '.join(sorted(extra))}")
        for key, sub in properties.items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
