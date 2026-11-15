"""End-to-end: one command produces every output, deterministically."""

import pytest

from recruiting_pipeline.pipeline import BI_TABLES, run_pipeline

EXPECTED = ["validation_report.md", "validation_report.json", "summary.md", "objection.md",
            "report.html", "kpis/funnel.csv", "kpis/source_effectiveness.csv",
            "kpis/time_to_fill.csv", "kpis/open_requisition_aging.csv",
            "kpis/recruiter_load.csv", "kpis/data_quality.csv", "figures/funnel.png"]


@pytest.fixture(scope="module")
def run_twice(tmp_path_factory):
    a, b = tmp_path_factory.mktemp("run_a"), tmp_path_factory.mktemp("run_b")
    res = run_pipeline(a / "raw", a / "out", bi_export=True)
    run_pipeline(b / "raw", b / "out")
    return res, a / "out", b / "out"


def test_all_outputs_written(run_twice):
    _, out, _ = run_twice
    for rel in EXPECTED:
        assert (out / rel).exists(), rel
    for table in BI_TABLES:
        assert (out / "bi" / f"{table}.csv").exists(), table


@pytest.mark.parametrize("rel", [p for p in EXPECTED if p.endswith((".csv", ".md", ".json"))])
def test_text_outputs_are_reproducible(run_twice, rel):
    _, a, b = run_twice
    assert (a / rel).read_text() == (b / rel).read_text()


def test_objection_shows_structural_effects(run_twice):
    obj = run_twice[0].objection.set_index("metric")
    assert obj.loc["Distinct source labels", "naive"] > obj.loc["Distinct source labels", "pipeline"]
    assert obj.loc["Minimum time-to-fill, days", "naive"] < 0
    assert obj.loc["Minimum time-to-fill, days", "pipeline"] > 0
    assert (obj.loc["CRM activities linked to an application", "naive"]
            < obj.loc["CRM activities linked to an application", "pipeline"])


def test_html_report_is_self_contained(run_twice):
    page = (run_twice[1] / "report.html").read_text()
    assert "data:image/png;base64," in page
    assert "all data is synthetic" in page
    assert "<script" not in page
