"""Orchestrates ingestion -> schema checks -> business rules, and writes the report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .findings import SEVERITY_ORDER, Finding
from .ingest import IngestResult, ingest
from .rules import run_rules
from .schemas import coerce_types, validate_schemas


@dataclass
class ValidationReport:
    ingest: IngestResult
    findings: list[Finding]

    @property
    def overall(self) -> str:
        return max((f.status for f in self.findings), key=SEVERITY_ORDER.get, default="OK")

    def counts(self) -> dict[str, int]:
        return {f.check_id: f.count for f in self.findings}

    def to_markdown(self) -> str:
        rows = {t: len(df) for t, df in self.ingest.tables.items()}
        lines = [
            "# Validation report",
            "",
            f"**Overall status: {self.overall}**",
            "",
            "## Inputs",
            "",
            "| File | Detected table |",
            "|---|---|",
            *[f"| `{f}` | {t} |" for f, t in self.ingest.file_map.items()],
            "",
            "| Table | Rows |",
            "|---|---:|",
            *[f"| {t} | {n:,} |" for t, n in rows.items()],
            "",
            "## Checks",
            "",
            "| Status | Layer | Table | Check | Rows | Action |",
            "|---|---|---|---|---:|---|",
        ]
        for f in sorted(self.findings, key=lambda x: (-SEVERITY_ORDER[x.status], x.layer)):
            lines.append(f"| [{f.status}] | {f.layer} | {f.table} | {f.check_id} | "
                         f"{f.count:,} | {f.action if f.count else '-'} |")
        lines += ["", "## Details", ""]
        for f in self.findings:
            if f.count:
                sample = ", ".join(f"`{s}`" for s in f.sample)
                lines.append(f"- **{f.check_id}** ({f.count:,}): {f.description}"
                             + (f" Sample: {sample}" if sample else ""))
        return "\n".join(lines) + "\n"


def run_validation(raw_dir: str | Path) -> ValidationReport:
    result = ingest(raw_dir)
    findings = list(result.findings)
    findings += validate_schemas(result.tables)
    findings += run_rules(coerce_types(result.tables))
    return ValidationReport(ingest=result, findings=findings)


def write_report(report: ValidationReport, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation_report.md").write_text(report.to_markdown())
    (out / "validation_report.json").write_text(json.dumps(
        {"overall": report.overall, "file_map": report.ingest.file_map,
         "findings": [f.to_dict() for f in report.findings]}, indent=2))
