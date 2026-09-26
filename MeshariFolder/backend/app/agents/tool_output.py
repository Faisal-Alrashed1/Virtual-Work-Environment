"""
Repair and sanity-check what a model returns for a forced tool call.

Found by running the real models (e2e_real_llm.py): Claude sometimes returns a
nested list — the Manager's `subtasks` — as a JSON *string* instead of a list.
`len()` of that string is large, so the "at least 5 subtasks" check passed, the
loop then iterated single *characters*, and `s["title"]` crashed with
"TypeError: string indices must be integers". A random 500 in the middle of a
demo, and invisible to every mocked test.

Three layers, all in llm_client.call_with_tool:
  1. REPAIR  what can be repaired for certain: a JSON string where the schema wants
             a list/object, a number sent as a string.
  2. CHECK   what would certainly crash the code: a required field missing, a list
             that isn't a list, a list shorter than the schema's minItems.
  3. RETRY / FAIL OVER when it can't be used: ask again (models are nondeterministic),
             then try the next provider, and only then give a clean 503 - never a 500.

Deliberately NOT checked here: what's *inside* list items (the Manager passes its
own `validate` for that). Item shapes vary between providers, and a check that
rejects output that used to work would be a regression we can't test without keys.
"""
import json
from typing import Any


class MalformedToolOutput(Exception):
    """The model's tool call can't be used as-is (and couldn't be repaired)."""


def _type_of(schema: dict):
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    return t


def repair_tool_input(value: Any, schema: dict) -> tuple[Any, list[str]]:
    """Fix what can be fixed with certainty. Returns (value, human-readable repairs).
    Input that is already correct comes back unchanged with no repairs."""
    repairs: list[str] = []

    def walk(v, s, path):
        if not isinstance(s, dict):
            return v
        t = _type_of(s)
        if isinstance(v, str) and t in ("array", "object"):
            try:
                parsed = json.loads(v)
            except ValueError:
                return v
            if (t == "array" and isinstance(parsed, list)) or (t == "object" and isinstance(parsed, dict)):
                repairs.append(f"'{path or 'input'}' was a JSON string; parsed it")
                v = parsed
            else:
                return v
        elif isinstance(v, str) and t in ("integer", "number"):
            try:
                number = float(v.strip())
            except ValueError:
                return v
            if t == "integer":
                if not number.is_integer():
                    return v
                number = int(number)
            repairs.append(f"'{path}' was a string; read it as the number {number}")
            return number
        if t == "object" and isinstance(v, dict):
            props = s.get("properties", {})
            return {k: walk(x, props.get(k), f"{path}.{k}" if path else k) for k, x in v.items()}
        if t == "array" and isinstance(v, list):
            return [walk(x, s.get("items"), f"{path}[{i}]") for i, x in enumerate(v)]
        return v

    return walk(value, schema, ""), repairs


def check_tool_input(data: Any, schema: dict) -> list[str]:
    """Problems that would crash the calling code; empty list = fine."""
    if not isinstance(data, dict):
        return ["the tool input is not an object"]
    problems = []
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in data or data[key] is None:
            problems.append(f"missing required field '{key}'")
    for key, value in data.items():
        s = props.get(key)
        if not isinstance(s, dict):
            continue
        t = _type_of(s)
        if t == "array":
            if not isinstance(value, list):
                problems.append(f"'{key}' should be a list, got {type(value).__name__}")
            elif len(value) < s.get("minItems", 0):
                problems.append(f"'{key}' has {len(value)} item(s), needs at least {s['minItems']}")
        elif t == "object" and not isinstance(value, dict):
            problems.append(f"'{key}' should be an object, got {type(value).__name__}")
    return problems
