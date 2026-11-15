"""Business rules, written by hand on purpose: each one encodes a piece of domain logic
that a reviewer should be able to read and challenge.

Every rule returns a Finding with the exact number of affected rows, what the
pipeline will do about them, and a small sample of ids for manual review.
"""

from __future__ import annotations

import pandas as pd

from .config import SOURCES
from .findings import Finding
from .normalize import normalize_application_refs, normalize_sources

SAMPLE = 5


def _ids(df: pd.DataFrame, col: str) -> list[str]:
    return df[col].astype(str).head(SAMPLE).tolist()


def duplicate_applications(apps: pd.DataFrame) -> Finding:
    data_cols = [c for c in apps.columns if c != "_source_file"]
    dup = apps[apps.duplicated(subset=data_cols, keep="first")]
    return Finding(
        "duplicate_applications", "applications", "business_rule", "WARN", len(dup),
        "Exact duplicate application rows (same values in every column).",
        "Keep the first occurrence, drop the rest.", _ids(dup, "application_id"))


def source_variants(apps: pd.DataFrame) -> list[Finding]:
    raw = apps["source"]
    mapped = normalize_sources(raw)
    variants = apps[raw.notna() & ~raw.isin(SOURCES) & mapped.notna()]
    unknown = apps[raw.notna() & mapped.isna()]
    return [
        Finding("source_variants", "applications", "business_rule", "WARN", len(variants),
                "Source labels spelled differently from the canonical list.",
                "Mapped to the canonical source name.",
                sorted(variants["source"].unique().tolist())[:SAMPLE]),
        Finding("unknown_sources", "applications", "business_rule", "ERROR", len(unknown),
                "Source labels that match no known source or variant.",
                "Grouped as 'Unknown' and listed for review.",
                sorted(unknown["source"].unique().tolist())[:SAMPLE]),
    ]


def hired_without_offer(apps: pd.DataFrame) -> Finding:
    """Funnel logic: a hire must have reached the 'hired' stage."""
    bad = apps[(apps["outcome"] == "hired") & apps["stage_reached"].notna()
               & (apps["stage_reached"] != "hired")]
    return Finding(
        "hired_without_offer", "applications", "business_rule", "ERROR", len(bad),
        "Outcome is 'hired' but the funnel stage never reached 'hired'.",
        "Excluded from conversion KPIs; flagged for the recruiting team.",
        _ids(bad, "application_id"))


def applied_before_opening(apps: pd.DataFrame, reqs: pd.DataFrame) -> list[Finding]:
    opened = apps["req_id"].map(reqs.drop_duplicates("req_id").set_index("req_id")["opened_at"])
    orphan = apps[opened.isna() & apps["req_id"].notna()]
    early = apps[opened.notna() & (apps["applied_at"] < opened)]
    return [
        Finding("applied_before_opening", "applications", "business_rule", "ERROR", len(early),
                "Application date earlier than the requisition's opening date.",
                "Excluded from time-based KPIs; flagged for review.",
                _ids(early, "application_id")),
        Finding("orphan_applications", "applications", "business_rule", "ERROR", len(orphan),
                "Applications whose requisition does not exist.",
                "Excluded from KPIs; flagged for review.", _ids(orphan, "application_id")),
    ]


def closed_before_opened(reqs: pd.DataFrame) -> Finding:
    bad = reqs[reqs["closed_at"].notna() & (reqs["closed_at"] < reqs["opened_at"])]
    return Finding(
        "closed_before_opened", "requisitions", "business_rule", "ERROR", len(bad),
        "Requisition closed before it was opened.",
        "Excluded from time-to-fill; flagged for review.", _ids(bad, "req_id"))


def crm_references(crm: pd.DataFrame, apps: pd.DataFrame) -> list[Finding]:
    raw = crm["application_ref"]
    norm = normalize_application_refs(raw)
    valid_ids = set(apps["application_id"].dropna())
    dirty = crm[norm.notna() & (raw != norm) & norm.isin(valid_ids)]
    orphan = crm[~norm.isin(valid_ids)]
    return [
        Finding("dirty_crm_keys", "crm_activities", "business_rule", "WARN", len(dirty),
                "CRM references with wrong case, extra spaces or a missing hyphen.",
                "Normalized to the canonical 'APP-00000' format.",
                raw[dirty.index].head(SAMPLE).tolist()),
        Finding("orphan_crm_activities", "crm_activities", "business_rule", "ERROR", len(orphan),
                "CRM activities whose application does not exist, even after normalization.",
                "Excluded from activity KPIs; listed for the CRM owner.",
                raw[orphan.index].head(SAMPLE).tolist()),
    ]


def run_rules(tables: dict[str, pd.DataFrame]) -> list[Finding]:
    reqs, apps, crm = tables["requisitions"], tables["applications"], tables["crm_activities"]
    return [
        duplicate_applications(apps),
        *source_variants(apps),
        hired_without_offer(apps),
        *applied_before_opening(apps, reqs),
        closed_before_opened(reqs),
        *crm_references(crm, apps),
    ]
