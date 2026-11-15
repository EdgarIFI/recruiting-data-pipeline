"""Single source of truth for the data contract: table columns, categories and sizes.

Everything else (generator, ingestion, schemas, rules) imports from here, so the
contract can only change in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Canonical column sets per table -------------------------------------------------
REQUISITION_COLUMNS = [
    "req_id", "client", "area", "city", "seniority",
    "openings", "opened_at", "closed_at", "status", "recruiter_id",
]
APPLICATION_COLUMNS = [
    "application_id", "candidate_id", "req_id", "source",
    "applied_at", "stage_reached", "outcome",
]
CRM_COLUMNS = [
    "activity_id", "application_ref", "activity_type", "activity_at", "recruiter_id",
]

TABLE_COLUMNS: dict[str, list[str]] = {
    "requisitions": REQUISITION_COLUMNS,
    "applications": APPLICATION_COLUMNS,
    "crm_activities": CRM_COLUMNS,
}

# Known historical renames in source exports (old name -> canonical name).
# Ingestion maps these and reports them as schema drift (WARN), never silently.
COLUMN_ALIASES: dict[str, str] = {
    "activity_date": "activity_at",
}

# --- Categories -----------------------------------------------------------------------
AREAS = ["Operations", "Sales", "Finance", "IT", "HR", "Logistics"]
CITIES = ["Monterrey", "Mexico City", "Guadalajara", "Queretaro", "Saltillo"]
SENIORITIES = ["Junior", "Mid", "Senior"]
REQ_STATUSES = ["open", "filled", "cancelled"]
RECRUITERS = [f"R{i:02d}" for i in range(1, 9)]
CLIENTS = [
    "Northwind Foods", "Cerro Logistics", "Altavista Retail", "Sierra Manufacturing",
    "Puerta Financial", "Brisa Telecom", "Roble Construction", "Lumen Health",
]

# Canonical sources; ingestion maps spelling variants onto these.
SOURCES = ["LinkedIn", "OCC", "Indeed", "Referral", "Computrabajo", "Career site"]

# Funnel stages in order; stage_reached is the furthest stage a candidate got to.
STAGES = ["applied", "screening", "interview", "offer", "hired"]
OUTCOMES = ["in_process", "rejected", "withdrawn", "hired"]
ACTIVITY_TYPES = ["call", "email", "interview", "offer_sent"]

ID_FORMATS = {
    "req_id": r"^REQ-\d{4}$",
    "application_id": r"^APP-\d{5}$",
    "candidate_id": r"^CND-\d{5}$",
    "activity_id": r"^ACT-\d{6}$",
    "recruiter_id": r"^R\d{2}$",
}


@dataclass(frozen=True)
class GenerationConfig:
    """Sizes and injected data-quality issues for the synthetic dataset.

    Every injected issue has an exact count. The generator records these counts in a
    manifest, and the tests assert that validation finds exactly that many: the
    validation layer is tested against known ground truth, not eyeballed.
    """

    seed: int = 2027
    n_requisitions: int = 120
    n_applications: int = 3000
    n_crm_activities: int = 6000
    n_crm_exports: int = 6
    start_date: str = "2026-01-05"
    horizon_days: int = 280
    drift_export: int = 4  # this periodic CRM export arrives with a renamed column

    injections: dict[str, int] = field(default_factory=lambda: {
        "duplicate_applications": 37,
        "source_variants": 120,
        "missing_stage": 15,
        "hired_without_offer": 9,
        "applied_before_opening": 21,
        "closed_before_opened": 6,
        "dirty_crm_keys": 250,
        "orphan_crm_activities": 44,
    })
