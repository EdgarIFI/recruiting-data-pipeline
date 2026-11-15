"""Synthetic data generator with exactly-counted, documented data-quality issues.

Design:
1. Generate a *clean* dataset whose internal logic is consistent (dates, funnel
   stages, references).
2. Inject each data-quality issue into a disjoint set of rows, so one issue can never
   mask or double-count another.
3. Record the exact count of every injected issue in a manifest. The validation
   layer is then tested against this ground truth.

All data is synthetic: names, clients and figures are invented.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    ACTIVITY_TYPES, AREAS, CITIES, CLIENTS, RECRUITERS, SENIORITIES, SOURCES, STAGES,
    GenerationConfig,
)

# File names imitate real exports on purpose: ingestion identifies tables by their
# columns, not by their file names.
REQUISITIONS_FILE = "ats_requisitions_export.csv"
APPLICATIONS_FILE = "ats_candidates_export.csv"
CRM_FILE_PATTERN = "crm_export_{:02d}.csv"
MANIFEST_FILE = "_manifest.json"

SOURCE_WEIGHTS = [0.34, 0.22, 0.16, 0.12, 0.10, 0.06]
# Probability of the furthest stage reached (applied ... hired).
STAGE_WEIGHTS = [0.38, 0.27, 0.20, 0.07, 0.08]

# Planted signals: real effects the analysis should *recover*, so it can be checked
# in both directions (finds true effects, does not invent false ones).
# 1) Referrals progress further in the funnel than every other source.
REFERRAL_STAGE_WEIGHTS = [0.20, 0.25, 0.27, 0.10, 0.18]
# 2) Time-to-fill grows with seniority (days from opening to closing, uniform range).
TIME_TO_FILL_DAYS = {"Junior": (10, 50), "Mid": (20, 70), "Senior": (35, 90)}
SOURCE_VARIANT_SPELLINGS = {
    "LinkedIn": ["linkedin", "Linked In", " LinkedIn "],
    "OCC": ["occ", "OCC Mundial"],
    "Indeed": ["indeed ", "INDEED"],
    "Referral": ["referral", "Referido"],
    "Computrabajo": ["CompuTrabajo", "computrabajo"],
    "Career site": ["career site", "Careers page"],
}


def _days(rng: np.random.Generator, low: int, high: int, size: int) -> pd.TimedeltaIndex:
    return pd.to_timedelta(rng.integers(low, high + 1, size=size), unit="D")


def _requisitions(cfg: GenerationConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg.n_requisitions
    start = pd.Timestamp(cfg.start_date)
    status = rng.choice(["filled", "open", "cancelled"], size=n, p=[0.55, 0.30, 0.15])
    # Requisitions still open at export time were opened recently; closed ones span
    # the whole period.
    opened = np.where(status == "open",
                      start + _days(rng, cfg.horizon_days - 120, cfg.horizon_days - 5, n),
                      start + _days(rng, 0, cfg.horizon_days - 100, n))
    opened = pd.DatetimeIndex(opened)
    seniority = rng.choice(SENIORITIES, size=n, p=[0.5, 0.35, 0.15])
    low = np.array([TIME_TO_FILL_DAYS[s][0] for s in seniority])
    high = np.array([TIME_TO_FILL_DAYS[s][1] for s in seniority])
    closed = opened + pd.to_timedelta(rng.integers(low, high + 1), unit="D")
    closed = pd.Series(closed).where(status != "open")
    return pd.DataFrame({
        "req_id": [f"REQ-{i:04d}" for i in range(1, n + 1)],
        "client": rng.choice(CLIENTS, size=n),
        "area": rng.choice(AREAS, size=n),
        "city": rng.choice(CITIES, size=n, p=[0.40, 0.25, 0.15, 0.12, 0.08]),
        "seniority": seniority,
        "openings": rng.integers(1, 4, size=n),
        "opened_at": opened,
        "closed_at": closed.values,
        "status": status,
        "recruiter_id": rng.choice(RECRUITERS, size=n),
    })


def _applications(cfg: GenerationConfig, rng: np.random.Generator,
                  reqs: pd.DataFrame) -> pd.DataFrame:
    n = cfg.n_applications
    req_idx = rng.integers(0, len(reqs), size=n)
    req = reqs.iloc[req_idx].reset_index(drop=True)
    # Applications arrive after opening and before closing (closed requisitions) or
    # before the export date (open ones). No event is ever after the export date.
    snapshot = pd.Timestamp(cfg.start_date) + pd.Timedelta(days=cfg.horizon_days)
    end = req["closed_at"].fillna(snapshot)
    window = (end - req["opened_at"]).dt.days.clip(upper=45)
    applied = req["opened_at"] + pd.to_timedelta(
        np.floor(rng.random(n) * (window.to_numpy() + 1)), unit="D")
    source = rng.choice(SOURCES, size=n, p=SOURCE_WEIGHTS)
    stage = np.where(source == "Referral",
                     rng.choice(STAGES, size=n, p=REFERRAL_STAGE_WEIGHTS),
                     rng.choice(STAGES, size=n, p=STAGE_WEIGHTS))

    # Outcome must agree with the stage and with the requisition status.
    outcome = np.where(stage == "hired", "hired", "rejected")
    not_hired = stage != "hired"
    open_req = (req["status"] == "open").to_numpy()
    roll = rng.random(n)
    outcome = np.where(not_hired & open_req & (roll < 0.6), "in_process", outcome)
    outcome = np.where(not_hired & (roll >= 0.85), "withdrawn", outcome)

    apps = pd.DataFrame({
        "application_id": [f"APP-{i:05d}" for i in range(1, n + 1)],
        "candidate_id": [f"CND-{i:05d}" for i in rng.permutation(n) + 1],
        "req_id": req["req_id"],
        "source": source,
        "applied_at": applied,
        "stage_reached": stage,
        "outcome": outcome,
    })
    return _enforce_hiring_consistency(apps, reqs, rng)


def _enforce_hiring_consistency(apps: pd.DataFrame, reqs: pd.DataFrame,
                                rng: np.random.Generator) -> pd.DataFrame:
    """Hires must agree with the requisition: filled -> 1..openings hires,
    open -> fewer hires than openings, cancelled -> no hires.

    Extra hires are demoted to 'offer' (offer declined); a filled requisition without
    a hire promotes its furthest-progressed applicant.
    """
    apps = apps.copy()
    rank = {s: i for i, s in enumerate(STAGES)}
    req_info = reqs.set_index("req_id")[["status", "openings"]]
    for req_id, grp in apps.groupby("req_id", sort=True):
        status, openings = req_info.loc[req_id, "status"], int(req_info.loc[req_id, "openings"])
        max_hires = {"filled": openings, "open": openings - 1, "cancelled": 0}[status]
        hired = grp.index[grp["outcome"] == "hired"].to_numpy()
        if len(hired) > max_hires:
            extra = rng.choice(hired, size=len(hired) - max_hires, replace=False)
            apps.loc[extra, ["stage_reached", "outcome"]] = ["offer", "rejected"]
        if status == "filled" and len(hired) == 0:
            best = grp["stage_reached"].map(rank).idxmax()
            apps.loc[best, ["stage_reached", "outcome"]] = ["hired", "hired"]
    return apps


def _crm(cfg: GenerationConfig, rng: np.random.Generator,
         apps: pd.DataFrame) -> pd.DataFrame:
    n = cfg.n_crm_activities
    snapshot = pd.Timestamp(cfg.start_date) + pd.Timedelta(days=cfg.horizon_days)
    app = apps.iloc[rng.integers(0, len(apps), size=n)].reset_index(drop=True)
    stage_rank = app["stage_reached"].map({s: i for i, s in enumerate(STAGES)}).to_numpy()
    # Interviews and offers can only exist if the candidate reached that stage.
    activity = np.where(stage_rank >= 3, rng.choice(ACTIVITY_TYPES, size=n),
                        np.where(stage_rank >= 2, rng.choice(ACTIVITY_TYPES[:3], size=n),
                                 rng.choice(ACTIVITY_TYPES[:2], size=n)))
    return pd.DataFrame({
        "activity_id": [f"ACT-{i:06d}" for i in range(1, n + 1)],
        "application_ref": app["application_id"],
        "activity_type": activity,
        "activity_at": app["applied_at"] + pd.to_timedelta(
            np.floor(rng.random(n) * (np.minimum(30, (snapshot - app["applied_at"]).dt.days) + 1)),
            unit="D"),
        "recruiter_id": rng.choice(RECRUITERS, size=n),
    })


def _take(pool: list[int], k: int) -> list[int]:
    """Pop k indices from a shuffled pool, so every injection gets disjoint rows."""
    if k > len(pool):
        raise ValueError("Not enough clean rows left to inject issues without overlap.")
    taken, pool[:] = pool[:k], pool[k:]
    return taken


def _inject(cfg: GenerationConfig, rng: np.random.Generator, reqs: pd.DataFrame,
            apps: pd.DataFrame, crm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inj = cfg.injections
    reqs, apps, crm = reqs.copy(), apps.copy(), crm.copy()

    # --- requisitions: closed before opened ---
    closed_pool = list(rng.permutation(np.flatnonzero(reqs["status"] != "open")))
    rows = _take(closed_pool, inj["closed_before_opened"])
    reqs.loc[rows, "closed_at"] = reqs.loc[rows, "opened_at"] - _days(rng, 1, 15, len(rows))

    # --- applications: one disjoint block per issue ---
    pool = list(rng.permutation(len(apps)))

    rows = _take(pool, inj["source_variants"])
    apps.loc[rows, "source"] = [
        rng.choice(SOURCE_VARIANT_SPELLINGS[s]) for s in apps.loc[rows, "source"]
    ]

    # Missing stage only on non-hired rows, so it cannot overlap the hired rule.
    non_hired = [i for i in pool if apps.at[i, "outcome"] != "hired"]
    rows = non_hired[: inj["missing_stage"]]
    taken = set(rows)
    pool = [i for i in pool if i not in taken]
    apps.loc[rows, "stage_reached"] = None

    rows = _take(pool, inj["hired_without_offer"])
    apps.loc[rows, "outcome"] = "hired"
    apps.loc[rows, "stage_reached"] = rng.choice(["screening", "interview"], size=len(rows))

    rows = _take(pool, inj["applied_before_opening"])
    opened = apps.loc[rows, "req_id"].map(reqs.set_index("req_id")["opened_at"])
    apps.loc[rows, "applied_at"] = (opened - _days(rng, 1, 20, len(rows))).to_numpy()

    rows = _take(pool, inj["duplicate_applications"])
    apps = pd.concat([apps, apps.loc[rows]], ignore_index=True)
    apps = apps.sample(frac=1, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)

    # --- CRM: dirty keys and orphan references on disjoint rows ---
    crm_pool = list(rng.permutation(len(crm)))
    rows = _take(crm_pool, inj["dirty_crm_keys"])
    styles = rng.integers(0, 3, size=len(rows))
    refs = crm.loc[rows, "application_ref"].to_numpy()
    crm.loc[rows, "application_ref"] = [
        r.lower() if s == 0 else f"  {r} " if s == 1 else r.replace("-", "")
        for r, s in zip(refs, styles)
    ]
    rows = _take(crm_pool, inj["orphan_crm_activities"])
    crm.loc[rows, "application_ref"] = [
        f"APP-{i:05d}" for i in rng.integers(90000, 99999, size=len(rows))
    ]
    return reqs, apps, crm


def generate(cfg: GenerationConfig | None = None) -> dict[str, pd.DataFrame | dict]:
    """Build the synthetic dataset in memory. Same config -> identical output."""
    cfg = cfg or GenerationConfig()
    rng = np.random.default_rng(cfg.seed)
    reqs = _requisitions(cfg, rng)
    apps = _applications(cfg, rng, reqs)
    crm = _crm(cfg, rng, apps)
    reqs, apps, crm = _inject(cfg, rng, reqs, apps, crm)
    manifest = {
        "seed": cfg.seed,
        "rows": {"requisitions": len(reqs), "applications": len(apps),
                 "crm_activities": len(crm)},
        "drift_export": cfg.drift_export,
        "injected": dict(cfg.injections),
        "config": asdict(cfg),
    }
    return {"requisitions": reqs, "applications": apps, "crm_activities": crm,
            "manifest": manifest}


def _to_csv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def write_raw(out_dir: str | Path, cfg: GenerationConfig | None = None) -> dict:
    """Write the dataset as raw 'export' files plus a ground-truth manifest."""
    cfg = cfg or GenerationConfig()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = generate(cfg)
    _to_csv(data["requisitions"], out / REQUISITIONS_FILE)
    _to_csv(data["applications"], out / APPLICATIONS_FILE)

    crm = data["crm_activities"].sort_values("activity_at").reset_index(drop=True)
    for k, chunk in enumerate(np.array_split(np.arange(len(crm)), cfg.n_crm_exports), start=1):
        part = crm.iloc[chunk]
        if k == cfg.drift_export:  # schema drift: an export arrives with an old column name
            part = part.rename(columns={"activity_at": "activity_date"})
        _to_csv(part, out / CRM_FILE_PATTERN.format(k))

    (out / MANIFEST_FILE).write_text(json.dumps(data["manifest"], indent=2, default=str))
    return data["manifest"]
