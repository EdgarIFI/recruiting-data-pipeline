"""The core claim of this repo: validation finds *exactly* what was injected — no more, no less."""

import pytest

from recruiting_pipeline.normalize import normalize_application_ref, normalize_source

# manifest key -> check_id in the validation report
INJECTION_TO_CHECK = {
    "duplicate_applications": "duplicate_applications",
    "source_variants": "source_variants",
    "missing_stage": "null_stage_reached",
    "hired_without_offer": "hired_without_offer",
    "applied_before_opening": "applied_before_opening",
    "closed_before_opened": "closed_before_opened",
    "dirty_crm_keys": "dirty_crm_keys",
    "orphan_crm_activities": "orphan_crm_activities",
}


@pytest.mark.parametrize("injection, check_id", INJECTION_TO_CHECK.items())
def test_each_injected_issue_found_exactly(report, manifest, injection, check_id):
    assert report.counts()[check_id] == manifest["injected"][injection]


def test_no_unexpected_findings(report):
    expected = set(INJECTION_TO_CHECK.values()) | {"schema_drift"}
    unexpected = {f.check_id: f.count for f in report.findings
                  if f.count and f.check_id not in expected}
    assert unexpected == {}


def test_clean_data_has_zero_false_positives(clean_report):
    flagged = {f.check_id: f.count for f in clean_report.findings if f.count}
    assert flagged == {}
    assert clean_report.overall == "OK"


def test_overall_status_is_worst_severity(report):
    assert report.overall == "ERROR"


def test_report_renders(report):
    md = report.to_markdown()
    assert "**Overall status: ERROR**" in md
    assert "| [ERROR] |" in md and "| [WARN] |" in md


@pytest.mark.parametrize("raw, expected", [
    ("LinkedIn", "LinkedIn"), (" LinkedIn ", "LinkedIn"), ("Linked In", "LinkedIn"),
    ("Referido", "Referral"), ("OCC Mundial", "OCC"), ("Careers page", "Career site"),
    ("Facebook", None), (None, None),
])
def test_normalize_source(raw, expected):
    assert normalize_source(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("APP-00012", "APP-00012"), ("app-00012", "APP-00012"), ("  APP-00012 ", "APP-00012"),
    ("APP00012", "APP-00012"), ("APP-12", None), ("CND-00012", None), (None, None),
])
def test_normalize_application_ref(raw, expected):
    assert normalize_application_ref(raw) == expected


@pytest.mark.parametrize("seed", [1, 7, 2026, 31337])
def test_exactness_holds_for_any_seed(tmp_path, seed):
    """Injections use disjoint rows, so exact counts must hold for every seed, not just the default one."""
    from recruiting_pipeline.config import GenerationConfig
    from recruiting_pipeline.generate import write_raw
    from recruiting_pipeline.validate import run_validation

    manifest = write_raw(tmp_path, GenerationConfig(seed=seed))
    counts = run_validation(tmp_path).counts()
    for injection, check_id in INJECTION_TO_CHECK.items():
        assert counts[check_id] == manifest["injected"][injection], (seed, check_id)
