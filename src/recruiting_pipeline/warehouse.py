"""DuckDB warehouse: load the cleaned tables, build the model, run the KPI queries.

The KPIs live in plain .sql files (src/recruiting_pipeline/sql/) so they can be
read, reviewed and reused outside Python.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd

from .clean import CleanResult
from .config import STAGES

SQL_PACKAGE = "recruiting_pipeline.sql"


def _sql(name: str) -> str:
    return resources.files(SQL_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def kpi_names() -> list[str]:
    files = resources.files(SQL_PACKAGE).iterdir()
    return sorted(f.name[len("kpi_"):-len(".sql")] for f in files
                  if f.name.startswith("kpi_") and f.name.endswith(".sql"))


def build_warehouse(cleaned: CleanResult, path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path))
    staging = {
        "stg_requisitions": cleaned.requisitions,
        "stg_applications": cleaned.applications,
        "stg_crm_activities": cleaned.crm_activities,
        "stg_dq_log": cleaned.dq_log,
        "stg_stages": pd.DataFrame({"stage": STAGES, "stage_rank": range(len(STAGES))}),
    }
    for name, df in staging.items():
        con.register(name, df)
    con.execute(_sql("model.sql"))
    for name in staging:
        con.unregister(name)
    return con


def run_kpis(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    return {name: con.execute(_sql(f"kpi_{name}.sql")).df() for name in kpi_names()}


def as_of(con: duckdb.DuckDBPyConnection) -> str:
    return str(con.execute("SELECT as_of FROM params").fetchone()[0])
