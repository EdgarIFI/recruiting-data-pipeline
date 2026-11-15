"""Business rules, written by hand on purpose: each one encodes a piece of domain logic
that a reviewer should be able to read and challenge.

Each rule is a *mask* (a boolean Series over the rows it judges). The same masks are
used twice:
- validation turns them into Findings (counts + action + sample ids);
- cleaning (clean.py) turns them into row-level data-quality flags.
So what the report counts is, by construction, exactly what the pipeline flags.
"""

from __future__ import annotations

import pandas as pd

from .config import SOURCES
from .findings import Finding
from .normalize import normalize_application_refs, normalize_sources

SAMPLE = 5


# --- masks: applications ----------------------------------------------------------------
def mask_duplicate_applications(apps: pd.DataFrame) -> pd.Series:
    """Exact duplicates (every data column equal); the first occurrence is not flagged."""
    data_cols = [c for c in apps.columns if not c.startswith("_")]
    return apps.duplicated(subset=data_cols, keep="first")


def mask_source_variants(apps: pd.DataFrame) -> pd.Series:
    raw = apps["source"]
    return raw.notna() & ~raw.isin(SOURCES) & normalize_sources(raw).notna()


def mask_unknown_sources(apps: pd.DataFrame) -> pd.Series:
    raw = apps["source"]
    return raw.notna() & normalize_sources(raw).isna()


def mask_missing_stage(apps: pd.DataFrame) -> pd.Series:
    return apps["stage_reached"].isna()


def mask_hired_without_offer(apps: pd.DataFrame) -> pd.Series:
    """Funnel logic: a hire must have reached the 'hired' stage."""
    return ((apps["outcome"] == "hired") & apps["stage_reached"].notna()
            & (apps["stage_reached"] != "hired"))


def _opened_at(apps: pd.DataFrame, reqs: pd.DataFrame) -> pd.Series:
    return apps["req_id"].map(reqs.drop_duplicates("req_id").set_index("req_id")["opened_at"])


def mask_applied_before_opening(apps: pd.DataFrame, reqs: pd.DataFrame) -> pd.Series:
    opened = _opened_at(apps, reqs)
    return opened.notna() & (apps["applied_at"] < opened)


def mask_orphan_applications(apps: pd.DataFrame, reqs: pd.DataFrame) -> pd.Series:
    return apps["req_id"].notna() & ~apps["req_id"].isin(set(reqs["req_id"]))


# --- masks: requisitions ----------------------------------------------------------------
def mask_closed_before_opened(reqs: pd.DataFrame) -> pd.Series:
    return reqs["closed_at"].notna() & (reqs["closed_at"] < reqs["opened_at"])


# --- masks: CRM -------------------------------------------------------------------------
def mask_dirty_crm_keys(crm: pd.DataFrame, apps: pd.DataFrame) -> pd.Series:
    raw = crm["application_ref"]
    norm = normalize_application_refs(raw)
    return norm.notna() & (raw != norm) & norm.isin(set(apps["application_id"].dropna()))


def mask_orphan_crm(crm: pd.DataFrame, apps: pd.DataFrame) -> pd.Series:
    norm = normalize_application_refs(crm["application_ref"])
    return ~norm.isin(set(apps["application_id"].dropna()))


# --- findings ---------------------------------------------------------------------------
def _finding(check_id: str, table: str, severity: str, df: pd.DataFrame, mask: pd.Series,
             description: str, action: str, sample_col: str) -> Finding:
    hits = df[mask]
    sample = hits[sample_col].astype(str).drop_duplicates().head(SAMPLE).tolist()
    return Finding(check_id, table, "business_rule", severity, int(mask.sum()),
                   description, action, sample)


def run_rules(tables: dict[str, pd.DataFrame]) -> list[Finding]:
    reqs, apps, crm = tables["requisitions"], tables["applications"], tables["crm_activities"]
    A, R, C = "applications", "requisitions", "crm_activities"
    return [
        _finding("duplicate_applications", A, "WARN", apps, mask_duplicate_applications(apps),
                 "Exact duplicate application rows (same values in every column).",
                 "Keep the first occurrence, drop the rest.", "application_id"),
        _finding("source_variants", A, "WARN", apps, mask_source_variants(apps),
                 "Source labels spelled differently from the canonical list.",
                 "Mapped to the canonical source name.", "source"),
        _finding("unknown_sources", A, "ERROR", apps, mask_unknown_sources(apps),
                 "Source labels that match no known source or variant.",
                 "Grouped as 'Unknown' and listed for review.", "source"),
        _finding("hired_without_offer", A, "ERROR", apps, mask_hired_without_offer(apps),
                 "Outcome is 'hired' but the funnel stage never reached 'hired'.",
                 "Excluded from funnel KPIs; flagged for the recruiting team.", "application_id"),
        _finding("applied_before_opening", A, "ERROR", apps,
                 mask_applied_before_opening(apps, reqs),
                 "Application date earlier than the requisition's opening date.",
                 "Excluded from funnel KPIs; flagged for review.", "application_id"),
        _finding("orphan_applications", A, "ERROR", apps, mask_orphan_applications(apps, reqs),
                 "Applications whose requisition does not exist.",
                 "Excluded from KPIs; flagged for review.", "application_id"),
        _finding("closed_before_opened", R, "ERROR", reqs, mask_closed_before_opened(reqs),
                 "Requisition closed before it was opened.",
                 "Excluded from time-to-fill; flagged for review.", "req_id"),
        _finding("dirty_crm_keys", C, "WARN", crm, mask_dirty_crm_keys(crm, apps),
                 "CRM references with wrong case, extra spaces or a missing hyphen.",
                 "Normalized to the canonical 'APP-00000' format.", "application_ref"),
        _finding("orphan_crm_activities", C, "ERROR", crm, mask_orphan_crm(crm, apps),
                 "CRM activities whose application does not exist, even after normalization.",
                 "Excluded from activity KPIs; listed for the CRM owner.", "application_ref"),
    ]
