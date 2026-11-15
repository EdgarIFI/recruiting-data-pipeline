"""Command-line entry point.

    recruiting-pipeline generate --out data/raw --seed 2027
    recruiting-pipeline validate --raw data/raw --reports reports
"""

from __future__ import annotations

import argparse
import sys

from .config import GenerationConfig
from .generate import write_raw
from .validate import run_validation, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recruiting-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

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

    report = run_validation(args.raw)
    write_report(report, args.reports)
    print(f"Overall status: {report.overall}")
    for f in report.findings:
        print(f"  [{f.status:5}] {f.check_id:28} {f.count:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
