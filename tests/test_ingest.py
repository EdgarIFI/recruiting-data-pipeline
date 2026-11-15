import pandas as pd

from recruiting_pipeline.ingest import identify_table, ingest


def test_tables_identified_by_content(dirty_raw):
    result = ingest(dirty_raw)
    assert result.file_map["ats_requisitions_export.csv"] == "requisitions"
    assert result.file_map["ats_candidates_export.csv"] == "applications"
    assert all(t == "crm_activities" for f, t in result.file_map.items() if f.startswith("crm_"))


def test_renamed_file_still_detected(tmp_path, dirty_raw):
    # A file name that says nothing about its content is still recognized.
    (tmp_path / "export_final_v2 (1).csv").write_text(
        (dirty_raw / "ats_requisitions_export.csv").read_text())
    assert ingest(tmp_path).file_map["export_final_v2 (1).csv"] == "requisitions"


def test_schema_drift_is_mapped_and_reported(dirty_raw):
    result = ingest(dirty_raw)
    drift = next(f for f in result.findings if f.check_id == "schema_drift")
    assert drift.count == 1 and "activity_date->activity_at" in drift.sample[0]
    assert "activity_date" not in result.tables["crm_activities"].columns
    assert result.tables["crm_activities"]["activity_at"].notna().all()


def test_unknown_file_is_flagged_not_guessed(tmp_path):
    pd.DataFrame({"foo": [1], "bar": [2]}).to_csv(tmp_path / "mystery.csv", index=False)
    result = ingest(tmp_path)
    assert result.file_map["mystery.csv"] == "unknown"
    assert next(f for f in result.findings if f.check_id == "unknown_files").count == 1


def test_identify_table_scores():
    table, score = identify_table(["activity_id", "application_ref", "activity_type",
                                   "activity_date", "recruiter_id"])
    assert table == "crm_activities" and score == 1.0


def test_sources_are_never_modified(dirty_raw):
    before = {p.name: p.stat().st_mtime_ns for p in dirty_raw.glob("*.csv")}
    ingest(dirty_raw)
    after = {p.name: p.stat().st_mtime_ns for p in dirty_raw.glob("*.csv")}
    assert before == after
