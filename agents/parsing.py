"""Tolerant JSON extraction for small local models.

Lightweight LLMs frequently wrap JSON in prose or ```json fences. We pull out
the first balanced JSON object/array we can find and parse that, raising a
clear error when nothing usable is present so the retry logic can react.
"""

from __future__ import annotations

import json
import re

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(raw_text: str) -> dict | list:
    fenced = _FENCE_PATTERN.search(raw_text)
    candidate = fenced.group(1).strip() if fenced else raw_text.strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    for opening, closing in (("{", "}"), ("[", "]")):
        start = candidate.find(opening)
        end = candidate.rfind(closing)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No parseable JSON found in model output: {raw_text[:200]!r}")
