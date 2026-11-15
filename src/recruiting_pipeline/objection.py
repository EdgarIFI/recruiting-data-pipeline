"""Objection step: try to break our own conclusions.

Question: does the pipeline actually change any answer, or is it ceremony?
We compute the same headline metrics twice:
  naive    - raw exports, typed but otherwise untouched (no dedup, no mapping,
             no exclusions, exact-match joins);
  pipeline - cleaned tables, KPI-eligible rows only.
The honest result is reported either way, including metrics that barely move.
"""

from __future__ import annotations

import numbers

import pandas as pd

from .clean import CleanResult
from .schemas import coerce_types


def _hire_rate_filled(apps: pd.DataFrame, reqs: pd.DataFrame) -> float:
    filled = set(reqs.loc[reqs["status"] == "filled", "req_id"])
    sub = apps[apps["req_id"].isin(filled)]
    return float((sub["outcome"] == "hired").mean())


def _interview_rate(apps: pd.DataFrame, reqs: pd.DataFrame, source: str) -> tuple[float, int]:
    filled = set(reqs.loc[reqs["status"] == "filled", "req_id"])
    sub = apps[apps["req_id"].isin(filled) & (apps["source"] == source)]
    reached = sub["stage_reached"].isin(["interview", "offer", "hired"])
    return float(reached.mean()), len(sub)


def compare(raw_tables: dict[str, pd.DataFrame], cleaned: CleanResult) -> pd.DataFrame:
    raw = coerce_types(raw_tables)
    r_reqs, r_apps, r_crm = raw["requisitions"], raw["applications"], raw["crm_activities"]
    c_reqs = cleaned.requisitions
    c_apps = cleaned.applications[cleaned.applications["kpi_eligible"]]
    c_crm = cleaned.crm_activities

    r_ttf = (r_reqs["closed_at"] - r_reqs["opened_at"]).dt.days[r_reqs["status"] == "filled"]
    c_ttf = c_reqs.loc[c_reqs["ttf_eligible"], "time_to_fill_days"].astype(float)

    r_ref_rate, r_ref_n = _interview_rate(r_apps, r_reqs, "Referral")
    c_ref_rate, c_ref_n = _interview_rate(c_apps, c_reqs, "Referral")

    r_linked = r_crm["application_ref"].isin(set(r_apps["application_id"])).mean()
    c_linked = c_crm["kpi_eligible"].mean()

    small_labels = (r_apps["source"].value_counts() < 30).sum()

    rows = [
        ("Applications counted", len(r_apps), len(c_apps),
         "Duplicates and untrustworthy rows inflate volume."),
        ("Distinct source labels", r_apps["source"].nunique(), c_apps["source"].nunique(),
         "Spelling variants split one channel into many."),
        ("Source labels with < 30 applications", int(small_labels),
         int((c_apps["source"].value_counts() < 30).sum()),
         "Tiny fake 'channels' that no one should rank."),
        ("Referral applications (filled reqs)", r_ref_n, c_ref_n,
         "Variants such as 'Referido' are lost from the Referral bucket."),
        ("Referral interview rate (filled reqs)", round(r_ref_rate, 4), round(c_ref_rate, 4),
         "The planted signal survives; the naive sample is just smaller."),
        ("Hire rate (filled reqs)", round(_hire_rate_filled(r_apps, r_reqs), 4),
         round(_hire_rate_filled(c_apps, c_reqs), 4),
         "Barely moves: the defects are ~3% of rows."),
        ("Median time-to-fill, days", float(r_ttf.median()), float(c_ttf.median()),
         "Medians are robust to a handful of bad dates."),
        ("Minimum time-to-fill, days", float(r_ttf.min()), float(c_ttf.min()),
         "Negative durations are impossible; they poison means and minimums."),
        ("CRM activities linked to an application", round(float(r_linked), 4),
         round(float(c_linked), 4),
         "Exact-match joins silently drop activities with dirty keys."),
    ]
    # dtype=object keeps counts as integers next to rates (no silent upcast to float)
    return pd.DataFrame(rows, columns=["metric", "naive", "pipeline", "why_it_matters"],
                        dtype=object)


def to_markdown(df: pd.DataFrame) -> str:
    lines = [
        "# Objection: does the pipeline change any answer?",
        "",
        "Same metrics computed on the raw exports (naive) and on the cleaned, "
        "KPI-eligible data (pipeline).",
        "",
        "| Metric | Naive | Pipeline | Why it matters |",
        "|---|---:|---:|---|",
    ]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.metric} | {_fmt(r.naive)} | {_fmt(r.pipeline)} | {r.why_it_matters} |")
    lines += [
        "",
        "**Reading.** Headline *rates* barely move, because the injected defects touch only "
        "a few percent of rows. What the pipeline changes is *structure*: channels are no "
        "longer split into spelling variants, impossible durations disappear, and CRM "
        "activity is linked to the right candidates. A naive analysis would not be very "
        "wrong on averages; it would be wrong on rankings, minimums and joins, and nobody "
        "would notice.",
        "",
    ]
    return "\n".join(lines)


def _fmt(v: object) -> str:
    if isinstance(v, numbers.Integral):
        return f"{int(v):,}"
    if isinstance(v, numbers.Real):
        v = float(v)
        return f"{v:.1%}" if 0 <= v <= 1 and not v.is_integer() else f"{v:g}"
    return str(v)
