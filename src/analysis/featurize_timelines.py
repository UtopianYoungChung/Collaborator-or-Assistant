"""
Feature extraction for PR timeline datasets under `data/raw/`.

Writes one JSONL row per PR timeline (top-level key).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, Optional

from src.analysis.stream_pr_timelines import iter_timeline_items


_REPO_RE = re.compile(r"/repos/([^/]+/[^/]+)/")


def _parse_iso8601_utc(s: str) -> Optional[datetime]:
    # Observed timestamps are like "2025-07-01T21:35:22Z".
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@dataclass
class TimelineFeaturizer:
    pr_key: str
    tool_family: str

    n_items: int = 0
    n_items_with_event: int = 0
    n_items_with_body: int = 0
    total_body_chars: int = 0

    event_counts: Counter[str] = field(default_factory=Counter)
    transition_counts: Counter[str] = field(default_factory=Counter)
    _prev_event: Optional[str] = None

    actors: set[str] = field(default_factory=set)
    repo: Optional[str] = None

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def update(self, item: Dict) -> None:
        self.n_items += 1

        ev = item.get("event")
        if isinstance(ev, str):
            self.n_items_with_event += 1
            self.event_counts[ev] += 1
            if self._prev_event is not None:
                self.transition_counts[f"{self._prev_event}->{ev}"] += 1
            self._prev_event = ev

        body = item.get("body")
        if isinstance(body, str):
            self.n_items_with_body += 1
            self.total_body_chars += len(body)

        actor = item.get("actor")
        if isinstance(actor, dict):
            login = actor.get("login")
            if isinstance(login, str):
                self.actors.add(login)

        user = item.get("user")
        if isinstance(user, dict):
            login = user.get("login")
            if isinstance(login, str):
                self.actors.add(login)

        if self.repo is None:
            for url_field in ("url", "html_url", "issue_url", "pull_request_url", "commit_url"):
                v = item.get(url_field)
                if not isinstance(v, str):
                    continue
                m = _REPO_RE.search(v)
                if m:
                    self.repo = m.group(1)
                    break

        created_at = item.get("created_at")
        if isinstance(created_at, str):
            dt = _parse_iso8601_utc(created_at)
            if dt is not None:
                if self.start_time is None or dt < self.start_time:
                    self.start_time = dt
                if self.end_time is None or dt > self.end_time:
                    self.end_time = dt

    def finalize(self) -> Dict:
        feats: Dict[str, int | float | str | None] = {
            "tool_family": self.tool_family,
            "pr_key": self.pr_key,
            "repo": self.repo,
            "n_items": self.n_items,
            "n_items_with_event": self.n_items_with_event,
            "n_unique_actors": len(self.actors),
            "n_items_with_body": self.n_items_with_body,
            "total_body_chars": self.total_body_chars,
        }
        if self.start_time is not None and self.end_time is not None:
            feats["duration_seconds"] = (self.end_time - self.start_time).total_seconds()
        else:
            feats["duration_seconds"] = None

        for ev, c in self.event_counts.items():
            feats[f"ev:{ev}"] = c
        for tr, c in self.transition_counts.items():
            feats[f"tr:{tr}"] = c
        return feats


def tool_family_from_dataset_filename(name: str) -> str:
    stem = Path(name).name
    if not stem.startswith("pr_timelines_") or not stem.endswith(".json"):
        return stem
    return stem[len("pr_timelines_") : -len(".json")]


def iter_feature_rows_for_file(
    dataset_path: str | Path,
    tool_family: str,
    max_prs: Optional[int] = None,
    max_items_per_pr: Optional[int] = None,
) -> Iterator[Dict]:
    prs_done = 0
    current: Optional[TimelineFeaturizer] = None
    items_seen_in_current = 0

    for ti in iter_timeline_items(dataset_path):
        if ti.item is None:
            if current is not None:
                yield current.finalize()
                prs_done += 1
                if max_prs is not None and prs_done >= max_prs:
                    return
            current = None
            items_seen_in_current = 0
            continue

        if current is None:
            current = TimelineFeaturizer(pr_key=ti.pr_key, tool_family=tool_family)
            items_seen_in_current = 0

        if max_items_per_pr is not None and items_seen_in_current >= max_items_per_pr:
            continue

        current.update(ti.item)
        items_seen_in_current += 1


def write_features_jsonl(
    dataset_dir: str | Path,
    output_jsonl: str | Path,
    max_prs_per_file: Optional[int] = None,
    max_items_per_pr: Optional[int] = None,
) -> None:
    dataset_dir = Path(dataset_dir)
    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)

    dataset_files = sorted(dataset_dir.glob("pr_timelines_*.json"))
    with out.open("w", encoding="utf-8") as f:
        for fp in dataset_files:
            tool_family = tool_family_from_dataset_filename(fp.name)
            for row in iter_feature_rows_for_file(
                fp,
                tool_family=tool_family,
                max_prs=max_prs_per_file,
                max_items_per_pr=max_items_per_pr,
            ):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

