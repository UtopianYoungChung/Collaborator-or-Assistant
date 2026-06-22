"""
Streaming parser for the PR timeline datasets.

Grounding (observed in this workspace):
- The datasets live under `data/raw/` as `pr_timelines_*.json`.
- Each file is a JSON object mapping a key like `"3193888615.json"` to an array of timeline-item objects.
- Files can be large, so this module avoids loading the full JSON into memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Dict, Iterator, Optional


_TOP_KEY_RE = re.compile(r'^\s*"([^"]+\.json)"\s*:\s*\[\s*$')


@dataclass(frozen=True)
class TimelineItem:
    pr_key: str
    item: Optional[Dict]  # None marks end-of-PR


def iter_timeline_items(path: str | Path) -> Iterator[TimelineItem]:
    """
    Yield timeline items in a single pass.

    Output protocol:
    - Yields TimelineItem(pr_key=<key>, item=<dict>) for each parsed array element object.
    - Yields TimelineItem(pr_key=<key>, item=None) exactly once at the end of each PR array.

    Notes:
    - Resilient to braces inside JSON strings (tracks string/escape state).
    - Only yields *object* elements (JSON dicts). Non-dict elements are ignored.
    """
    p = Path(path)
    current_pr_key: Optional[str] = None
    in_pr_array = False

    # State for extracting one JSON object element at a time.
    capturing = False
    buf_chars: list[str] = []
    brace_depth = 0
    in_string = False
    escape = False

    def _reset_object_capture() -> None:
        nonlocal capturing, buf_chars, brace_depth, in_string, escape
        capturing = False
        buf_chars = []
        brace_depth = 0
        in_string = False
        escape = False

    def _feed_char(ch: str) -> Optional[str]:
        """
        Feed a character into the object extractor.
        Returns a completed JSON object string when finished, else None.
        """
        nonlocal capturing, brace_depth, in_string, escape

        if not capturing:
            if ch == "{":
                capturing = True
                buf_chars.append(ch)
                brace_depth = 1
            return None

        buf_chars.append(ch)

        if escape:
            escape = False
            return None

        if ch == "\\":
            if in_string:
                escape = True
            return None

        if ch == '"':
            in_string = not in_string
            return None

        if in_string:
            return None

        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0:
                s = "".join(buf_chars)
                _reset_object_capture()
                return s

        return None

    def _finish_pr_array(pr_key: str) -> Iterator[TimelineItem]:
        _reset_object_capture()
        yield TimelineItem(pr_key=pr_key, item=None)

    with p.open("r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            if not in_pr_array:
                m = _TOP_KEY_RE.match(raw_line)
                if m:
                    current_pr_key = m.group(1)
                    in_pr_array = True
                    _reset_object_capture()
                continue

            assert current_pr_key is not None

            stripped = raw_line.lstrip()
            if not capturing and (stripped.startswith("]") or stripped.startswith("],")):
                yield from _finish_pr_array(current_pr_key)
                current_pr_key = None
                in_pr_array = False
                continue

            for ch in raw_line:
                obj_s = _feed_char(ch)
                if obj_s is None:
                    continue
                try:
                    parsed = json.loads(obj_s)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    yield TimelineItem(pr_key=current_pr_key, item=parsed)

    if in_pr_array and current_pr_key is not None:
        yield from _finish_pr_array(current_pr_key)

