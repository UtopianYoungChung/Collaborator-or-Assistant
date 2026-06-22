"""
Temporal trend analysis for PR workflows.

This script summarizes how PR volume and collaboration-type distributions vary over time,
grounded in per-event timestamps available in `data/raw/`.

Method (deterministic):
- For each PR workflow, compute the earliest available timestamp across its events
  (using the canonical timestamp extraction in `src.analysis.workflows.analyze_workflow`).
- Bucket PRs by month (YYYY-MM) and quarter (YYYY-Qx).
- Aggregate counts by tool and collaboration type.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.analysis.stream_pr_timelines import iter_timeline_items
from src.analysis.workflows import CollaborationType, DATASET_DIR, FILES, analyze_workflow


def _iter_pr_event_lists(dataset_path: Path) -> Iterable[Tuple[str, List[dict]]]:
    current_key: Optional[str] = None
    current_events: List[dict] = []
    for ti in iter_timeline_items(dataset_path):
        if ti.item is None:
            if current_key is not None:
                yield current_key, current_events
            current_key = None
            current_events = []
            continue
        if current_key is None:
            current_key = ti.pr_key
        current_events.append(ti.item)


def _parse_iso(ts: str) -> Optional[datetime]:
    # Expect ISO-8601-like strings; normalize trailing Z.
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _quarter_key(dt: datetime) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year:04d}-Q{q}"


@dataclass
class TemporalStats:
    total_prs: int
    prs_with_timestamp: int
    prs_missing_timestamp: int
    min_timestamp_utc: Optional[str]
    max_timestamp_utc: Optional[str]
    # Aggregates
    counts_by_tool_by_month: Dict[str, Dict[str, int]]
    counts_by_type_by_quarter: Dict[str, Dict[str, int]]


def compute_temporal_stats() -> TemporalStats:
    total_prs = 0
    with_ts = 0
    missing_ts = 0
    min_dt: Optional[datetime] = None
    max_dt: Optional[datetime] = None

    # tool -> month -> count
    tool_month: Dict[str, Counter[str]] = {tool: Counter() for tool in FILES.keys()}
    # type -> quarter -> count
    type_quarter: Dict[str, Counter[str]] = {ct.value: Counter() for ct in CollaborationType}

    for tool, filename in FILES.items():
        fp = DATASET_DIR / filename
        for pr_id, pr_events in _iter_pr_event_lists(fp):
            total_prs += 1
            wf = analyze_workflow(pr_id, pr_events, tool, ml_analyzer=None)

            # Earliest timestamp across normalized workflow events
            pr_min: Optional[datetime] = None
            for ev in wf.events:
                if not ev.timestamp:
                    continue
                dt = _parse_iso(ev.timestamp)
                if dt is None:
                    continue
                pr_min = dt if pr_min is None or dt < pr_min else pr_min

            if pr_min is None:
                missing_ts += 1
                continue

            with_ts += 1
            min_dt = pr_min if min_dt is None or pr_min < min_dt else min_dt
            max_dt = pr_min if max_dt is None or pr_min > max_dt else max_dt

            m = _month_key(pr_min)
            q = _quarter_key(pr_min)
            tool_month[tool][m] += 1
            type_quarter[wf.collaboration_type.value][q] += 1

    return TemporalStats(
        total_prs=total_prs,
        prs_with_timestamp=with_ts,
        prs_missing_timestamp=missing_ts,
        min_timestamp_utc=min_dt.isoformat() if min_dt else None,
        max_timestamp_utc=max_dt.isoformat() if max_dt else None,
        counts_by_tool_by_month={t: dict(c) for t, c in tool_month.items()},
        counts_by_type_by_quarter={k: dict(c) for k, c in type_quarter.items()},
    )


def render_markdown(stats: TemporalStats, top_months: int = 24) -> str:
    lines: List[str] = []
    w = lines.append
    w("# Temporal Analysis")
    w("")
    w("## Coverage")
    w("")
    w(f"- **Total PRs**: {stats.total_prs:,}")
    w(f"- **PRs with at least one parsed timestamp**: {stats.prs_with_timestamp:,}")
    w(f"- **PRs missing/invalid timestamps**: {stats.prs_missing_timestamp:,}")
    w("")
    w("## Dataset time range (UTC; based on earliest event per PR)")
    w("")
    w(f"- **Min**: {stats.min_timestamp_utc}")
    w(f"- **Max**: {stats.max_timestamp_utc}")
    w("")

    # Tool-by-month table (show most recent months)
    all_months = set()
    for tool_counts in stats.counts_by_tool_by_month.values():
        all_months.update(tool_counts.keys())
    months_sorted = sorted(all_months)
    if months_sorted:
        months_show = months_sorted[-top_months:]
        w("## PR volume by tool (monthly; most recent months)")
        w("")
        w("| Month | " + " | ".join(FILES.keys()) + " | **TOTAL** |")
        w("|---|" + "|".join(["---:" for _ in FILES.keys()]) + "|---:|")
        for m in months_show:
            row = [m]
            tot = 0
            for tool in FILES.keys():
                k = int(stats.counts_by_tool_by_month.get(tool, {}).get(m, 0))
                tot += k
                row.append(f"{k:,}")
            row.append(f"**{tot:,}**")
            w("| " + " | ".join(row) + " |")
        w("")

    # Type-by-quarter table (all quarters)
    all_quarters = set()
    for type_counts in stats.counts_by_type_by_quarter.values():
        all_quarters.update(type_counts.keys())
    quarters_sorted = sorted(all_quarters)
    if quarters_sorted:
        w("## Collaboration type distribution over time (quarterly; all PRs)")
        w("")
        types = [ct.value for ct in CollaborationType]
        w("| Quarter | " + " | ".join(types) + " | **TOTAL** |")
        w("|---|" + "|".join(["---:" for _ in types]) + "|---:|")
        for q in quarters_sorted:
            row = [q]
            tot = 0
            for t in types:
                k = int(stats.counts_by_type_by_quarter.get(t, {}).get(q, 0))
                tot += k
                row.append(f"{k:,}")
            row.append(f"**{tot:,}**")
            w("| " + " | ".join(row) + " |")
        w("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(prog="src.analysis.temporal_trends")
    p.add_argument("--out-md", default="reports/temporal_analysis.md")
    p.add_argument("--out-json", default=".tmp/temporal_analysis.json")
    args = p.parse_args()

    stats = compute_temporal_stats()

    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_md.write_text(render_markdown(stats), encoding="utf-8")
    out_json.write_text(json.dumps(asdict(stats), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

