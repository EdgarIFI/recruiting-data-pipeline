"""Cleaning must flag exactly what validation reported, and never lose a row silently."""

import pytest

from recruiting_pipeline.clean import clean
from recruiting_pipeline.config import SOURCES
from recruiting_pipeline.ingest import ingest

# check_id in the data-quality log -> check_id in the validation report
LOG_TO_REPORT = {
    "duplicate_applications": "duplicate_applications",
    "source_variants": "source_variants",
    "missing_stage": "null_stage_reached",
    "hired_without_offer": "hired_without_offer",
    "applied_before_opening": "applied_before_opening",
    "closed_before_opened": "closed_before_opened",
    "dirty_crm_keys": "dirty_crm_keys",
    "orphan_crm_activities": "orphan_crm_activities",
}


@pytest.fixture(scope="module")
def cleaned(dirty_raw):
    return clean(ingest(dirty_raw).tables)


def test_log_matches_validation_report(cleaned, report):
    logged = cleaned.dq_log.groupby("check_id").size().to_dict()
    for log_id, report_id in LOG_TO_REPORT.items():
        assert logged.get(log_id, 0) == report.counts()[report_id], log_id


def test_only_duplicates_are_dropped(cleaned, report, manifest):
    raw_rows = report.ingest.tables["applications"].shape[0]
    assert len(cleaned.applications) == raw_rows - manifest["injected"]["duplicate_applications"]
    assert not cleaned.applications.duplicated("application_id").any()
    assert len(cleaned.requisitions) == manifest["rows"]["requisitions"]
    assert len(cleaned.crm_activities) == manifest["rows"]["crm_activities"]


def test_sources_are_canonical_after_cleaning(cleaned, manifest):
    assert set(cleaned.applications["source"]) <= set(SOURCES) | {"Unknown"}
    # the raw label is kept for traceability
    changed = (cleaned.applications["source_raw"] != cleaned.applications["source"]).sum()
    assert changed == manifest["injected"]["source_variants"]


def test_eligibility_excludes_exactly_the_error_rows(cleaned, manifest):
    inj = manifest["injected"]
    expected_excluded = (inj["missing_stage"] + inj["hired_without_offer"]
                         + inj["applied_before_opening"])
    assert (~cleaned.applications["kpi_eligible"]).sum() == expected_excluded
    assert (~cleaned.crm_activities["kpi_eligible"]).sum() == inj["orphan_crm_activities"]


def test_no_impossible_durations_survive(cleaned):
    eligible = cleaned.requisitions[cleaned.requisitions["ttf_eligible"]]
    assert (eligible["time_to_fill_days"] > 0).all()


def test_crm_keys_normalized(cleaned):
    linked = cleaned.crm_activities[cleaned.crm_activities["kpi_eligible"]]
    assert linked["application_id"].str.fullmatch(r"APP-\d{5}").all()
