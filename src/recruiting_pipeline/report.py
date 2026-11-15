"""Static report: figures (matplotlib), a summary in Markdown and a self-contained HTML page.

Interactive exploration is deliberately left to the BI layer (Power BI, built on the
exported model). This report has to be readable on GitHub, in an email or printed,
with no server and no JavaScript.

Visual rules: one hue per single-series chart, thin marks, recessive grid, direct
labels on the values that matter, status colors (warning/critical) reserved for
data quality and always paired with a text label.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Reference palette (light mode).
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"
SERIES_LIGHT = "#86b6ef"
STATUS = {"ERROR": "#d03b3b", "WARN": "#fab219"}

FIGURES = {
    "funnel": "Hiring funnel (filled requisitions)",
    "source_interview_rate": "Interview rate by source, with 95% interval",
    "time_to_fill": "Time-to-fill by seniority",
    "open_aging": "Open requisitions by age",
    "data_quality": "What the pipeline fixed and excluded",
}


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _figure(height: float = 3.2) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(7.2, height), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    return fig, ax


def _title(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, color=TEXT, fontweight="bold", pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=TEXT_2)


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)


def fig_funnel(kpis: dict[str, pd.DataFrame], path: Path) -> None:
    df = kpis["funnel"].query("cohort == 'filled_requisitions'").iloc[::-1]
    fig, ax = _figure()
    ax.barh(df["stage"], df["reached"], color=SERIES, height=0.62, edgecolor=SURFACE, linewidth=2)
    top = df["reached"].max()
    for y, (n, conv) in enumerate(zip(df["reached"], df["conversion_from_previous"])):
        label = f"{n:,}" if pd.isna(conv) else f"{n:,}  ({conv:.0%} of previous stage)"
        ax.text(n + top * 0.01, y, label, va="center", fontsize=9, color=TEXT)
    ax.set_xlim(0, top * 1.45)
    ax.tick_params(axis="y", labelcolor=TEXT, labelsize=10)
    _title(ax, FIGURES["funnel"], "Applications that reached each stage; outcomes are final")
    _save(fig, path)


def fig_source(kpis: dict[str, pd.DataFrame], path: Path) -> None:
    df = kpis["source_effectiveness"].sort_values("interview_rate")
    fig, ax = _figure(3.4)
    y = range(len(df))
    ax.hlines(y, df["interview_rate_low"], df["interview_rate_high"], color=SERIES_LIGHT, linewidth=3)
    ax.plot(df["interview_rate"], y, "o", color=SERIES, markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    for i, (r, n) in enumerate(zip(df["interview_rate"], df["applications"])):
        ax.text(df["interview_rate_high"].iloc[i] + 0.01, i, f"{r:.0%}  (n={n:,})",
                va="center", fontsize=9, color=TEXT)
    ax.set_yticks(list(y), df["source"])
    ax.tick_params(axis="y", labelcolor=TEXT, labelsize=10)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, max(df["interview_rate_high"]) + 0.2)
    ax.set_ylim(-0.6, len(df) - 0.4)
    _title(ax, FIGURES["source_interview_rate"],
           "Filled requisitions. Overlapping intervals = no evidence of a difference")
    _save(fig, path)


def fig_time_to_fill(kpis: dict[str, pd.DataFrame], path: Path) -> None:
    order = ["Junior", "Mid", "Senior"]
    df = (kpis["time_to_fill"].query("dimension == 'seniority'")
          .set_index("value").loc[order].reset_index())
    fig, ax = _figure(2.6)
    y = range(len(df))
    ax.hlines(y, df["p25_days"], df["p75_days"], color=SERIES_LIGHT, linewidth=6)
    ax.plot(df["median_days"], y, "o", color=SERIES, markersize=9,
            markeredgecolor=SURFACE, markeredgewidth=2)
    for i, r in df.iterrows():
        ax.text(r["p75_days"] + 1.5, i, f"median {r['median_days']:.0f} days  (n={r['filled_requisitions']})",
                va="center", fontsize=9, color=TEXT)
    ax.set_yticks(list(y), df["value"])
    ax.tick_params(axis="y", labelcolor=TEXT, labelsize=10)
    ax.set_xlim(0, df["p75_days"].max() + 45)
    ax.set_ylim(-0.6, len(df) - 0.4)
    ax.set_xlabel("days from opening to closing (bar = interquartile range)", color=TEXT_2, fontsize=9)
    _title(ax, FIGURES["time_to_fill"], "Filled requisitions with valid dates")
    _save(fig, path)


def fig_open_aging(kpis: dict[str, pd.DataFrame], path: Path) -> None:
    df = kpis["open_requisition_aging"]
    fig, ax = _figure(2.6)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.bar(df["bucket"], df["open_requisitions"], color=SERIES, width=0.6,
           edgecolor=SURFACE, linewidth=2)
    for x, n in enumerate(df["open_requisitions"]):
        ax.text(x, n + 0.3, str(n), ha="center", fontsize=9, color=TEXT)
    ax.tick_params(axis="x", labelcolor=TEXT, labelsize=10)
    _title(ax, FIGURES["open_aging"], "Days open at the snapshot date")
    _save(fig, path)


def fig_data_quality(kpis: dict[str, pd.DataFrame], path: Path) -> None:
    df = kpis["data_quality"].iloc[::-1]
    fig, ax = _figure(3.4)
    colors = [STATUS[s] for s in df["severity"]]
    ax.barh(df["check_id"], df["affected_rows"], color=colors, height=0.62,
            edgecolor=SURFACE, linewidth=2)
    top = df["affected_rows"].max()
    for y, (n, sev) in enumerate(zip(df["affected_rows"], df["severity"])):
        ax.text(n + top * 0.01, y, f"{n:,}  {sev}", va="center", fontsize=9, color=TEXT)
    ax.set_xlim(0, top * 1.3)
    ax.tick_params(axis="y", labelcolor=TEXT, labelsize=9)
    _title(ax, FIGURES["data_quality"], "WARN = fixed automatically · ERROR = excluded from KPIs and flagged")
    _save(fig, path)


def write_figures(kpis: dict[str, pd.DataFrame], out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams["svg.hashsalt"] = "recruiting-pipeline"
    makers = {"funnel": fig_funnel, "source_interview_rate": fig_source,
              "time_to_fill": fig_time_to_fill, "open_aging": fig_open_aging,
              "data_quality": fig_data_quality}
    paths = {}
    for name, make in makers.items():
        paths[name] = out / f"{name}.png"
        make(kpis, paths[name])
    return paths


def summary_markdown(kpis: dict[str, pd.DataFrame], as_of: str, objection_md: str) -> str:
    f = kpis["funnel"].query("cohort == 'filled_requisitions'").set_index("stage")
    ttf = kpis["time_to_fill"].query("dimension == 'overall'").iloc[0]
    src = kpis["source_effectiveness"].iloc[0]
    aging = kpis["open_requisition_aging"]
    stale = int(aging.loc[aging["bucket"] == "90+ days", "open_requisitions"].sum())
    lines = [
        "# Summary",
        "",
        f"Snapshot date: {as_of}. All data is synthetic.",
        "",
        "| KPI | Value |",
        "|---|---:|",
        f"| Applications on filled requisitions | {int(f.loc['applied', 'reached']):,} |",
        f"| Applied → interview | {f.loc['interview', 'share_of_applicants']:.1%} |",
        f"| Applied → hired | {f.loc['hired', 'share_of_applicants']:.1%} |",
        f"| Median time-to-fill | {ttf['median_days']:.0f} days (IQR {ttf['p25_days']:.0f}–{ttf['p75_days']:.0f}) |",
        f"| Best source by interview rate | {src['source']} {src['interview_rate']:.0%} "
        f"(95% CI {src['interview_rate_low']:.0%}–{src['interview_rate_high']:.0%}) |",
        f"| Open requisitions older than 90 days | {stale} of {int(aging['open_requisitions'].sum())} |",
        "",
        objection_md,
    ]
    return "\n".join(lines)


def _table_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, classes="t", na_rep="–", float_format=lambda x: f"{x:,.4g}")


def _img(path: Path, alt: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'


def write_html(kpis: dict[str, pd.DataFrame], figures: dict[str, Path], as_of: str,
               validation_overall: str, objection: pd.DataFrame, path: Path) -> None:
    sections = []
    tables = {"funnel": "funnel", "source_interview_rate": "source_effectiveness",
              "time_to_fill": "time_to_fill", "open_aging": "open_requisition_aging",
              "data_quality": "data_quality"}
    for name, title in FIGURES.items():
        sections.append(
            f"<section><h2>{html.escape(title)}</h2>{_img(figures[name], title)}"
            f"<details><summary>Data table</summary>{_table_html(kpis[tables[name]])}</details></section>")
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Recruiting funnel report (synthetic data)</title>
<style>
  .viz-root {{ --surface-1:{SURFACE}; --text-primary:{TEXT}; --text-secondary:{TEXT_2}; --grid:{GRID}; }}
  body {{ margin:0; background:var(--surface-1); color:var(--text-primary);
         font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  main {{ max-width:860px; margin:0 auto; padding:32px 20px 64px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:18px; margin:36px 0 8px; }}
  .meta {{ color:var(--text-secondary); margin:0 0 24px; }}
  img {{ max-width:100%; height:auto; display:block; }}
  details {{ margin-top:8px; }} summary {{ cursor:pointer; color:var(--text-secondary); }}
  table.t {{ border-collapse:collapse; font-size:13px; margin:8px 0; width:100%; }}
  table.t th, table.t td {{ text-align:right; padding:4px 8px; border-bottom:1px solid var(--grid); }}
  table.t th:first-child, table.t td:first-child {{ text-align:left; }}
  .note {{ border-left:3px solid var(--grid); padding:4px 12px; color:var(--text-secondary); }}
</style></head>
<body class="viz-root"><main>
<h1>Recruiting funnel report</h1>
<p class="meta">Snapshot {html.escape(as_of)} · validation status: {html.escape(validation_overall)} ·
<strong>all data is synthetic</strong></p>
<p class="note">Every KPI is computed only on rows that passed validation. Fixed issues (WARN) and
excluded rows (ERROR) are listed in the last chart. Source code:
github.com/EdgarIFI/recruiting-data-pipeline</p>
{''.join(sections)}
<section><h2>Objection: does the pipeline change any answer?</h2>
{_table_html(objection)}</section>
<p class="meta">Code and documentation developed with AI assistance (Claude); problem framing,
design decisions and validation are my own.</p>
</main></body></html>
"""
    path.write_text(page, encoding="utf-8")
