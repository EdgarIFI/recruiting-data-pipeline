"""Schema layer (pandera): types, nullability, formats and allowed values, per table.

Division of labour (hybrid approach):
- pandera answers "is each column well-formed?" (declarative, one row at a time).
- rules.py answers "does the data make business sense?" (cross-field and
  cross-table logic written by hand, where the reasoning should stay visible).
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from .config import (
    ACTIVITY_TYPES, AREAS, CITIES, CLIENTS, ID_FORMATS, OUTCOMES, REQ_STATUSES,
    SENIORITIES, STAGES,
)
from .findings import Finding


def _id(name: str, unique: bool = False) -> pa.Column:
    return pa.Column(str, pa.Check.str_matches(ID_FORMATS[name]), unique=unique)


SCHEMAS: dict[str, pa.DataFrameSchema] = {
    "requisitions": pa.DataFrameSchema(
        {
            "req_id": _id("req_id", unique=True),
            "client": pa.Column(str, pa.Check.isin(CLIENTS)),
            "area": pa.Column(str, pa.Check.isin(AREAS)),
            "city": pa.Column(str, pa.Check.isin(CITIES)),
            "seniority": pa.Column(str, pa.Check.isin(SENIORITIES)),
            "openings": pa.Column("Int64", pa.Check.in_range(1, 10), coerce=True),
            "opened_at": pa.Column(pa.DateTime, coerce=True),
            "closed_at": pa.Column(pa.DateTime, coerce=True, nullable=True),
            "status": pa.Column(str, pa.Check.isin(REQ_STATUSES)),
            "recruiter_id": _id("recruiter_id"),
        },
        strict=False,  # lineage column _source_file is allowed
    ),
    "applications": pa.DataFrameSchema(
        {
            # Uniqueness of application_id is a business rule (exact duplicates are
            # fixable), so it is not enforced here.
            "application_id": _id("application_id"),
            "candidate_id": _id("candidate_id"),
            "req_id": _id("req_id"),
            # Spelling variants are fixable -> handled as a business rule, not here.
            "source": pa.Column(str),
            "applied_at": pa.Column(pa.DateTime, coerce=True),
            "stage_reached": pa.Column(str, pa.Check.isin(STAGES)),
            "outcome": pa.Column(str, pa.Check.isin(OUTCOMES)),
        },
        strict=False,
    ),
    "crm_activities": pa.DataFrameSchema(
        {
            "activity_id": _id("activity_id", unique=True),
            # Dirty keys are fixable -> business rule.
            "application_ref": pa.Column(str),
            "activity_type": pa.Column(str, pa.Check.isin(ACTIVITY_TYPES)),
            "activity_at": pa.Column(pa.DateTime, coerce=True),
            "recruiter_id": _id("recruiter_id"),
        },
        strict=False,
    ),
}


def _check_name(check: object) -> str:
    text = str(check)
    if text.startswith("not_nullable"):
        return "null"
    return text.split("(")[0]


def validate_schemas(tables: dict[str, pd.DataFrame]) -> list[Finding]:
    """Validate every table lazily (collect *all* failures) and turn them into Findings."""
    findings: list[Finding] = []
    for name, schema in SCHEMAS.items():
        df = tables[name]
        try:
            schema.validate(df, lazy=True)
            findings.append(Finding(
                f"schema_{name}", name, "schema", "ERROR", 0,
                "All columns have the expected type, format and allowed values."))
        except SchemaErrors as err:
            cases = err.failure_cases
            cases = cases[cases["column"].notna()]
            for (column, check), grp in cases.groupby(["column", "check"], dropna=False):
                rows = grp["index"].dropna().unique()
                kind = _check_name(check)
                findings.append(Finding(
                    check_id=f"{kind}_{column}",
                    table=name, layer="schema", severity="ERROR",
                    count=int(len(rows)) if len(rows) else int(len(grp)),
                    description=f"Column '{column}' fails check '{check}'.",
                    action="Rows excluded from KPIs and listed for review.",
                    sample=[str(v) for v in grp["failure_case"].astype(str).unique()[:5]],
                ))
    return findings


def coerce_types(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Typed copies for the business rules (bad values become NaT/NA, never crash)."""
    out = {}
    for name, df in tables.items():
        df = df.copy()
        for col in df.columns:
            if col.endswith("_at"):
                df[col] = pd.to_datetime(df[col], errors="coerce")
        if "openings" in df:
            df["openings"] = pd.to_numeric(df["openings"], errors="coerce").astype("Int64")
        out[name] = df
    return out
