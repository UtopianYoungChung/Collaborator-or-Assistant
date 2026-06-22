"""
End-to-end ML pipeline (aligned to current workspace layout):
1) Stream feature extraction from `data/raw/pr_timelines_*.json` -> JSONL
2) Train/evaluate a baseline multinomial Naive Bayes classifier

Run from repo root:
  python -m src.analysis.pipeline run --max-prs-per-file 50
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analysis.featurize_timelines import write_features_jsonl
from src.analysis.train_nb import (
    MultinomialNB,
    _iter_jsonl,
    train_and_eval,
    train_test_split_rows,
    save_model,
)


def cmd_extract(args: argparse.Namespace) -> None:
    out = Path(args.output)
    write_features_jsonl(
        dataset_dir=args.dataset_dir,
        output_jsonl=out,
        max_prs_per_file=args.max_prs_per_file,
        max_items_per_pr=args.max_items_per_pr,
    )
    print(f"Wrote features to: {out}")


def cmd_train(args: argparse.Namespace) -> None:
    report = train_and_eval(
        features_jsonl=args.features,
        test_fraction=args.test_fraction,
        seed=args.seed,
        alpha=args.alpha,
    )
    print(json.dumps(report, indent=2))

    if args.save_model:
        # Fit the saved model on the TRAIN split only, using the same
        # deterministic split as train_and_eval. Fitting on all rows would
        # leak the test PRs into the model and inflate the reported held-out
        # accuracy (see PART II/robustness/nb_reproduction_2026-06-20.md).
        rows = list(_iter_jsonl(args.features))
        train_rows, _ = train_test_split_rows(
            rows, test_fraction=args.test_fraction, seed=args.seed
        )
        model = MultinomialNB(alpha=args.alpha).fit(train_rows)
        save_model(model, args.save_model)
        print(f"Saved model to: {args.save_model}")


def cmd_run(args: argparse.Namespace) -> None:
    cmd_extract(args)
    train_args = argparse.Namespace(
        features=args.output,
        test_fraction=args.test_fraction,
        seed=args.seed,
        alpha=args.alpha,
        save_model=args.save_model,
    )
    cmd_train(train_args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="src.analysis.pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="Extract per-PR features to JSONL")
    pe.add_argument("--dataset-dir", default="data/raw", help="Directory containing pr_timelines_*.json")
    pe.add_argument("--output", default=".tmp/features.jsonl", help="Output JSONL path")
    pe.add_argument("--max-prs-per-file", type=int, default=None, help="Limit PRs per dataset file (smoke testing)")
    pe.add_argument("--max-items-per-pr", type=int, default=None, help="Limit timeline items per PR (smoke testing)")
    pe.set_defaults(func=cmd_extract)

    pt = sub.add_parser("train", help="Train/evaluate Naive Bayes classifier on extracted features")
    pt.add_argument("--features", default=".tmp/features.jsonl", help="Input JSONL produced by extract step")
    pt.add_argument("--test-fraction", type=float, default=0.2, help="Test fraction for deterministic split")
    pt.add_argument("--seed", type=int, default=0, help="Seed for deterministic split")
    pt.add_argument("--alpha", type=float, default=1.0, help="Laplace smoothing alpha")
    pt.add_argument("--save-model", default=None, help="Optional path to save trained model JSON")
    pt.set_defaults(func=cmd_train)

    pr = sub.add_parser("run", help="Run extract then train")
    pr.add_argument("--dataset-dir", default="data/raw", help="Directory containing pr_timelines_*.json")
    pr.add_argument("--output", default=".tmp/features.jsonl", help="Output JSONL path")
    pr.add_argument("--max-prs-per-file", type=int, default=None, help="Limit PRs per dataset file (smoke testing)")
    pr.add_argument("--max-items-per-pr", type=int, default=None, help="Limit timeline items per PR (smoke testing)")
    pr.add_argument("--test-fraction", type=float, default=0.2, help="Test fraction for deterministic split")
    pr.add_argument("--seed", type=int, default=0, help="Seed for deterministic split")
    pr.add_argument("--alpha", type=float, default=1.0, help="Laplace smoothing alpha")
    pr.add_argument("--save-model", default=None, help="Optional path to save trained model JSON")
    pr.set_defaults(func=cmd_run)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

