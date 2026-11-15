"""Command-line entry point.

    recruiting-pipeline run --raw data/raw --out reports          # everything, end to end
    recruiting-pipeline run --raw data/raw --out reports --bi     # + model tables for Power BI
    recruiting-pipeline generate --out data/raw --seed 2027       # only the synthetic exports
    recruiting-pipeline validate --raw data/raw --reports reports # only the validation report
"""

from __future__ import annotations

import argparse
import sys

from .config import GenerationConfig
from .generate import write_raw
from .pipeline import run_pipeline
from .validate import run_validation, write_report


def _print_findings(findings) -> None:
    for f in findings:
        print(f"  [{f.status:5}] {f.check_id:28} {f.count:>6}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recruiting-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate (if needed), validate, clean, model, report.")
    run.add_argument("--raw", default="data/raw")
    run.add_argument("--out", default="reports")
    run.add_argument("--seed", type=int, default=2027)
    run.add_argument("--bi", action="store_true", help="Also export model tables as CSV for BI tools.")

    gen = sub.add_parser("generate", help="Write the synthetic raw exports.")
    gen.add_argument("--out", default="data/raw")
    gen.add_argument("--seed", type=int, default=2027)

    val = sub.add_parser("validate", help="Ingest and validate the raw exports.")
    val.add_argument("--raw", default="data/raw")
    val.add_argument("--reports", default="reports")

    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = write_raw(args.out, GenerationConfig(seed=args.seed))
        print(f"Wrote synthetic exports to {args.out}: {manifest['rows']}")
        return 0
    if args.command == "validate":
        report = run_validation(args.raw)
        write_report(report, args.reports)
        print(f"Overall status: {report.overall}")
        _print_findings(report.findings)
        return 0

    result = run_pipeline(args.raw, args.out, seed=args.seed, bi_export=args.bi)
    print(f"Validation: {result.validation.overall} · snapshot {result.as_of} · outputs in {args.out}/")
    _print_findings([f for f in result.validation.findings if f.count])
    return 0


if __name__ == "__main__":
    sys.exit(main())
