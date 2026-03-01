from __future__ import annotations

import json
from typing import Any


class JsonExtractionError(ValueError):
    pass


def extract_first_json_object(text: str) -> dict[str, Any]:
    """
    Extract the first top-level JSON object from free-form text.
    Supports common LLM patterns like fenced blocks and extra prose.
    """
    if not text:
        raise JsonExtractionError("empty response")

    # Fast path: try full text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    stripped = text.strip()
    # Remove fenced code block markers if present
    for fence in ("```json", "```JSON", "```"):
        if fence in stripped:
            stripped = stripped.replace(fence, "")
            stripped = stripped.replace("```", "").strip()

    # Bracket matching for the first {...}
    start = stripped.find("{")
    if start < 0:
        raise JsonExtractionError("no '{' found")

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(stripped)):
        ch = stripped[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : i + 1]
                try:
                    parsed = json.loads(candidate)
                    if not isinstance(parsed, dict):
                        raise JsonExtractionError("top-level json is not an object")
                    return parsed
                except Exception as e:
                    raise JsonExtractionError(f"invalid json: {e}")

    raise JsonExtractionError("unterminated json object")
