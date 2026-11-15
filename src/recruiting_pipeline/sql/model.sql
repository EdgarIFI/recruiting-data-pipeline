-- Analytical model (DuckDB). Built from the cleaned staging frames (stg_*).
-- Grain:
--   dim_requisition    one row per requisition
--   dim_stage          one row per funnel stage (ordered)
--   fact_application   one row per unique application (duplicates already removed)
--   fact_crm_activity  one row per CRM activity
--   dq_log             one row per (entity, data-quality check) affected

CREATE OR REPLACE TABLE dim_requisition AS
SELECT
    req_id, client, area, city, seniority,
    openings::INTEGER            AS openings,
    opened_at::DATE              AS opened_at,
    closed_at::DATE              AS closed_at,
    status, recruiter_id,
    time_to_fill_days::INTEGER   AS time_to_fill_days,
    ttf_eligible,
    dq_closed_before_opened
FROM stg_requisitions;

CREATE OR REPLACE TABLE dim_stage AS
SELECT stage, stage_rank::INTEGER AS stage_rank FROM stg_stages;

CREATE OR REPLACE TABLE fact_application AS
SELECT
    application_id, candidate_id, req_id,
    source, source_raw,
    applied_at::DATE             AS applied_at,
    stage_reached,
    stage_rank::INTEGER          AS stage_rank,
    outcome,
    kpi_eligible
FROM stg_applications;

CREATE OR REPLACE TABLE fact_crm_activity AS
SELECT
    activity_id, application_id, activity_type,
    activity_at::DATE            AS activity_at,
    recruiter_id,
    kpi_eligible
FROM stg_crm_activities;

CREATE OR REPLACE TABLE dq_log AS
SELECT table_name, entity_id, check_id, severity, action FROM stg_dq_log;

-- Snapshot date: the latest event in the data (data-driven, so KPIs are reproducible).
CREATE OR REPLACE VIEW params AS
SELECT GREATEST(
    (SELECT max(activity_at) FROM fact_crm_activity WHERE kpi_eligible),
    (SELECT max(applied_at)  FROM fact_application)
) AS as_of;

-- 95% Wilson score interval for a proportion k/n. Preferred over the normal
-- approximation because several sources have small n and rates near 0.
CREATE OR REPLACE MACRO wilson_low(k, n) AS
    (k::DOUBLE / n + pow(1.96, 2) / (2 * n)
     - 1.96 * sqrt(k::DOUBLE / n * (1 - k::DOUBLE / n) / n + pow(1.96, 2) / (4 * pow(n, 2))))
    / (1 + pow(1.96, 2) / n);

CREATE OR REPLACE MACRO wilson_high(k, n) AS
    (k::DOUBLE / n + pow(1.96, 2) / (2 * n)
     + 1.96 * sqrt(k::DOUBLE / n * (1 - k::DOUBLE / n) / n + pow(1.96, 2) / (4 * pow(n, 2))))
    / (1 + pow(1.96, 2) / n);
