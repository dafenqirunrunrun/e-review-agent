from __future__ import annotations
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCHEMA_DIR = BASE / "schema"
EXAMPLE_DIR = BASE / "examples"

def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


def _basic_check_schema(schema: dict, name: str) -> None:
    for key in ("$schema", "title", "type"):
        if key not in schema:
            fail(f"{name}: missing required schema keyword {key}")
    if schema.get("type") != "object":
        fail(f"{name}: top-level schema type must be object")
    if not isinstance(schema.get("properties", {}), dict):
        fail(f"{name}: properties must be an object")
    if not isinstance(schema.get("required", []), list):
        fail(f"{name}: required must be an array")


def _basic_validate(payload: dict, schema: dict, example_name: str) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in payload:
            errors.append(f"{example_name}: missing required field {key}")
    for key, value in payload.items():
        spec = properties.get(key)
        if not isinstance(spec, dict):
            continue
        expected = spec.get("type")
        if expected == "string" and not isinstance(value, str):
            errors.append(f"{example_name}: {key} must be string")
        elif expected == "integer" and not isinstance(value, int):
            errors.append(f"{example_name}: {key} must be integer")
        elif expected == "number" and not isinstance(value, (int, float)):
            errors.append(f"{example_name}: {key} must be number")
        elif expected == "boolean" and not isinstance(value, bool):
            errors.append(f"{example_name}: {key} must be boolean")
        elif expected == "array" and not isinstance(value, list):
            errors.append(f"{example_name}: {key} must be array")
        elif expected == "object" and not isinstance(value, dict):
            errors.append(f"{example_name}: {key} must be object")
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{example_name}: {key} value {value!r} not in enum")
    return errors

schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))
if not schema_files:
    fail(f"No schema files found in {SCHEMA_DIR}")

registry = {}
for path in schema_files:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.name}: invalid JSON: {exc}")
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(data)
    else:
        _basic_check_schema(data, path.name)
    registry[path.name] = data
    print(f"[PASS] schema structure: {path.name}")

# Validate selected examples after removing the explicit notice field.
pairs = [
    ("example_candidate.json", "dataset_candidate.schema.json"),
    ("example_annotation.json", "dataset_annotation.schema.json"),
]
for example_name, schema_name in pairs:
    example_path = EXAMPLE_DIR / example_name
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    payload.pop("_notice", None)
    if Draft202012Validator is not None:
        validator = Draft202012Validator(registry[schema_name])
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    else:
        errors = _basic_validate(payload, registry[schema_name], example_name)
    if errors:
        for err in errors:
            if isinstance(err, str):
                print(f"[ERROR] {err}")
            else:
                print(f"[ERROR] {example_name}: {'/'.join(map(str, err.path))}: {err.message}")
        fail(f"{example_name} does not validate")
    print(f"[PASS] example validation: {example_name}")

mode = "jsonschema" if Draft202012Validator is not None else "basic-offline"
print(f"[PASS] {len(schema_files)} schemas parsed and examples validated. validator={mode}")
