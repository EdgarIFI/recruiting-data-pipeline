"""Cleaning: apply deterministic fixes (WARN) and flag untrustworthy rows (ERROR).

Principles:
- Never delete a row silently. Exact duplicates are dropped (the only deletion) and
  logged; every other problem becomes a row-level flag plus a 'kpi_eligible' column.
- Reuse the validation masks (rules.py), so the data-quality log matches the
  validation report check by check.
- Sources stay untouched: cleaning works on copies of the ingested tables.

Order matters: duplicates are removed first, so the remaining flags refer to unique
rows.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import rules
from .config import STAGES
from .normalize import normalize_application_refs, normalize_sources
from .schemas import coerce_types


@dataclass
class CleanResult:
    requisitions: pd.DataFrame
    applications: pd.DataFrame
    crm_activities: pd.DataFrame
    dq_log: pd.DataFrame          # one row per (entity, check) affected

    def tables(self) -> dict[str, pd.DataFrame]:
        return {"requisitions": self.requisitions, "applications": self.applications,
                "crm_activities": self.crm_activities, "dq_log": self.dq_log}


def _log(df: pd.DataFrame, mask: pd.Series, table: str, id_col: str,
         check_id: str, severity: str, action: str) -> pd.DataFrame:
    return pd.DataFrame({
        "table_name": table, "entity_id": df.loc[mask, id_col].astype(str).to_numpy(),
        "check_id": check_id, "severity": severity, "action": action,
    })


def clean(raw_tables: dict[str, pd.DataFrame]) -> CleanResult:
    t = coerce_types(raw_tables)
    reqs, apps, crm = (t["requisitions"].copy(), t["applications"].copy(),
                       t["crm_activities"].copy())
    logs: list[pd.DataFrame] = []

    # --- requisitions -------------------------------------------------------------------
    bad_dates = rules.mask_closed_before_opened(reqs)
    logs.append(_log(reqs, bad_dates, "requisitions", "req_id", "closed_before_opened",
                     "ERROR", "excluded from time-to-fill"))
    reqs["dq_closed_before_opened"] = bad_dates
    reqs["time_to_fill_days"] = (reqs["closed_at"] - reqs["opened_at"]).dt.days.astype("Int64")
    reqs["ttf_eligible"] = (reqs["status"] == "filled") & reqs["closed_at"].notna() & ~bad_dates

    # --- applications -------------------------------------------------------------------
    dup = rules.mask_duplicate_applications(apps)
    logs.append(_log(apps, dup, "applications", "application_id", "duplicate_applications",
                     "WARN", "dropped (kept first occurrence)"))
    apps = apps[~dup].reset_index(drop=True)

    variants = rules.mask_source_variants(apps)
    unknown = rules.mask_unknown_sources(apps)
    logs.append(_log(apps, variants, "applications", "application_id", "source_variants",
                     "WARN", "mapped to canonical source"))
    logs.append(_log(apps, unknown, "applications", "application_id", "unknown_sources",
                     "ERROR", "grouped as 'Unknown'"))
    apps["source_raw"] = apps["source"]
    apps["source"] = normalize_sources(apps["source"]).fillna("Unknown")

    error_masks = {
        "missing_stage": rules.mask_missing_stage(apps),
        "hired_without_offer": rules.mask_hired_without_offer(apps),
        "applied_before_opening": rules.mask_applied_before_opening(apps, reqs),
        "orphan_applications": rules.mask_orphan_applications(apps, reqs),
    }
    for check_id, mask in error_masks.items():
        logs.append(_log(apps, mask, "applications", "application_id", check_id,
                         "ERROR", "excluded from funnel KPIs"))
        apps[f"dq_{check_id}"] = mask
    apps["stage_rank"] = apps["stage_reached"].map({s: i for i, s in enumerate(STAGES)}).astype("Int64")
    apps["kpi_eligible"] = ~pd.concat(error_masks, axis=1).any(axis=1)

    # --- CRM ----------------------------------------------------------------------------
    dirty = rules.mask_dirty_crm_keys(crm, apps)
    orphan = rules.mask_orphan_crm(crm, apps)
    logs.append(_log(crm, dirty, "crm_activities", "activity_id", "dirty_crm_keys",
                     "WARN", "reference normalized"))
    logs.append(_log(crm, orphan, "crm_activities", "activity_id", "orphan_crm_activities",
                     "ERROR", "excluded from activity KPIs"))
    crm["application_id"] = normalize_application_refs(crm["application_ref"])
    crm["dq_orphan"] = orphan
    crm["kpi_eligible"] = ~orphan

    rename = {"_source_file": "source_file"}
    dq_log = pd.concat(logs, ignore_index=True)
    return CleanResult(reqs.rename(columns=rename), apps.rename(columns=rename),
                       crm.rename(columns=rename), dq_log)
