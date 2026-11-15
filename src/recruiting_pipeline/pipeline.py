"""End-to-end run: generate (if needed) -> validate -> clean -> model -> KPIs -> objection -> report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .clean import CleanResult, clean
from .config import GenerationConfig
from .generate import write_raw
from .objection import compare
from .objection import to_markdown as objection_markdown
from .report import summary_markdown, write_figures, write_html
from .validate import ValidationReport, run_validation, write_report
from .warehouse import as_of, build_warehouse, run_kpis

BI_TABLES = ["dim_requisition", "dim_stage", "fact_application", "fact_crm_activity", "dq_log"]


@dataclass
class PipelineResult:
    validation: ValidationReport
    cleaned: CleanResult
    kpis: dict[str, pd.DataFrame]
    objection: pd.DataFrame
    as_of: str


def run_pipeline(raw_dir: str | Path, out_dir: str | Path, seed: int = 2027,
                 bi_export: bool = False) -> PipelineResult:
    raw, out = Path(raw_dir), Path(out_dir)
    if not any(raw.glob("*.csv")):
        write_raw(raw, GenerationConfig(seed=seed))

    validation = run_validation(raw)
    write_report(validation, out)

    cleaned = clean(validation.ingest.tables)
    con = build_warehouse(cleaned)
    kpis = run_kpis(con)
    snapshot = as_of(con)

    (out / "kpis").mkdir(parents=True, exist_ok=True)
    for name, df in kpis.items():
        df.to_csv(out / "kpis" / f"{name}.csv", index=False, float_format="%.4f")

    objection = compare(validation.ingest.tables, cleaned)
    objection_md = objection_markdown(objection)
    (out / "objection.md").write_text(objection_md, encoding="utf-8")
    (out / "summary.md").write_text(summary_markdown(kpis, snapshot, objection_md), encoding="utf-8")

    figures = write_figures(kpis, out / "figures")
    write_html(kpis, figures, snapshot, validation.overall, objection, out / "report.html")

    if bi_export:
        (out / "bi").mkdir(exist_ok=True)
        for table in BI_TABLES:
            con.execute(f"SELECT * FROM {table}").df().to_csv(out / "bi" / f"{table}.csv", index=False)
    con.close()
    return PipelineResult(validation, cleaned, kpis, objection, snapshot)
