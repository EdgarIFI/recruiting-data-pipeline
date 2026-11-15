"""KPIs: SQL results are cross-checked against an independent pandas implementation,
and the planted signals must be recovered (while noise must not be read as signal)."""

import numpy as np
import pandas as pd
import pytest

from recruiting_pipeline.clean import clean
from recruiting_pipeline.config import STAGES
from recruiting_pipeline.ingest import ingest
from recruiting_pipeline.warehouse import as_of, build_warehouse, kpi_names, run_kpis


@pytest.fixture(scope="module")
def cleaned(dirty_raw):
    return clean(ingest(dirty_raw).tables)


@pytest.fixture(scope="module")
def kpis(cleaned):
    con = build_warehouse(cleaned)
    out = run_kpis(con)
    out["_as_of"] = as_of(con)
    con.close()
    return out


@pytest.fixture(scope="module")
def filled_apps(cleaned):
    apps = cleaned.applications[cleaned.applications["kpi_eligible"]]
    filled = cleaned.requisitions.loc[cleaned.requisitions["status"] == "filled", "req_id"]
    return apps[apps["req_id"].isin(set(filled))]


def test_all_kpi_queries_present(kpis):
    assert set(kpi_names()) == {"data_quality", "funnel", "open_requisition_aging",
                                "recruiter_load", "source_effectiveness", "time_to_fill"}


# --- SQL vs pandas -------------------------------------------------------------------
def test_funnel_matches_pandas(kpis, filled_apps):
    sql = kpis["funnel"].query("cohort == 'filled_requisitions'").set_index("stage")["reached"]
    rank = filled_apps["stage_reached"].map({s: i for i, s in enumerate(STAGES)})
    for i, stage in enumerate(STAGES):
        assert sql[stage] == (rank >= i).sum(), stage


def test_source_effectiveness_matches_pandas(kpis, filled_apps):
    sql = kpis["source_effectiveness"].set_index("source")
    pdf = filled_apps.groupby("source").agg(
        applications=("application_id", "size"),
        hires=("outcome", lambda s: (s == "hired").sum()))
    for source, row in pdf.iterrows():
        assert sql.loc[source, "applications"] == row["applications"]
        assert sql.loc[source, "hires"] == row["hires"]


def test_wilson_interval_matches_reference(kpis):
    row = kpis["source_effectiveness"].iloc[0]
    k, n, z = row["reached_interview"], row["applications"], 1.96
    p = k / n
    center = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    assert row["interview_rate_low"] == pytest.approx(center - half, abs=1e-4)
    assert row["interview_rate_high"] == pytest.approx(center + half, abs=1e-4)


def test_time_to_fill_matches_pandas(kpis, cleaned):
    reqs = cleaned.requisitions[cleaned.requisitions["ttf_eligible"]]
    sql = kpis["time_to_fill"].set_index(["dimension", "value"])
    assert sql.loc[("overall", "All"), "median_days"] == pytest.approx(
        reqs["time_to_fill_days"].astype(float).median())
    for level, grp in reqs.groupby("seniority"):
        assert sql.loc[("seniority", level), "median_days"] == pytest.approx(
            grp["time_to_fill_days"].astype(float).median())


# --- internal consistency ------------------------------------------------------------
def test_rates_are_probabilities(kpis):
    se = kpis["source_effectiveness"]
    for col in ["interview_rate", "hire_rate", "interview_rate_low", "hire_rate_high"]:
        assert se[col].between(0, 1).all(), col
    assert (se["interview_rate_low"] <= se["interview_rate"]).all()
    assert (se["interview_rate"] <= se["interview_rate_high"]).all()


def test_aging_and_load_account_for_every_open_requisition(kpis, cleaned):
    n_open = (cleaned.requisitions["status"] == "open").sum()
    assert kpis["open_requisition_aging"]["open_requisitions"].sum() == n_open
    assert kpis["recruiter_load"]["open_requisitions"].sum() == n_open


def test_no_event_after_snapshot(kpis, cleaned):
    snapshot = pd.Timestamp(kpis["_as_of"])
    assert cleaned.applications["applied_at"].max() <= snapshot
    assert cleaned.crm_activities["activity_at"].max() <= snapshot


# --- planted signals -----------------------------------------------------------------
def test_planted_referral_signal_is_recovered(kpis):
    se = kpis["source_effectiveness"].set_index("source")
    ref_low = se.loc["Referral", "interview_rate_low"]
    others_high = se.drop("Referral")["interview_rate_high"]
    assert (ref_low > others_high).all()


def test_planted_seniority_signal_is_recovered(kpis):
    ttf = kpis["time_to_fill"].query("dimension == 'seniority'").set_index("value")["median_days"]
    assert ttf["Junior"] < ttf["Mid"] < ttf["Senior"]


def test_noise_is_not_read_as_signal(kpis):
    """No planted effect among non-referral sources: their intervals must all overlap."""
    se = kpis["source_effectiveness"].set_index("source").drop("Referral")
    assert se["interview_rate_low"].max() < se["interview_rate_high"].min()
