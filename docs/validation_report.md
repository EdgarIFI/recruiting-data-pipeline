# Validation report

**Overall status: ERROR**

## Inputs

| File | Detected table |
|---|---|
| `ats_candidates_export.csv` | applications |
| `ats_requisitions_export.csv` | requisitions |
| `crm_export_01.csv` | crm_activities |
| `crm_export_02.csv` | crm_activities |
| `crm_export_03.csv` | crm_activities |
| `crm_export_04.csv` | crm_activities |
| `crm_export_05.csv` | crm_activities |
| `crm_export_06.csv` | crm_activities |

| Table | Rows |
|---|---:|
| requisitions | 120 |
| applications | 3,037 |
| crm_activities | 6,000 |

## Checks

| Status | Layer | Table | Check | Rows | Action |
|---|---|---|---|---:|---|
| [ERROR] | business_rule | applications | hired_without_offer | 9 | Excluded from funnel KPIs; flagged for the recruiting team. |
| [ERROR] | business_rule | applications | applied_before_opening | 21 | Excluded from funnel KPIs; flagged for review. |
| [ERROR] | business_rule | requisitions | closed_before_opened | 6 | Excluded from time-to-fill; flagged for review. |
| [ERROR] | business_rule | crm_activities | orphan_crm_activities | 44 | Excluded from activity KPIs; listed for the CRM owner. |
| [ERROR] | schema | applications | null_stage_reached | 15 | Rows excluded from KPIs and listed for review. |
| [WARN] | business_rule | applications | duplicate_applications | 37 | Keep the first occurrence, drop the rest. |
| [WARN] | business_rule | applications | source_variants | 120 | Mapped to the canonical source name. |
| [WARN] | business_rule | crm_activities | dirty_crm_keys | 250 | Normalized to the canonical 'APP-00000' format. |
| [WARN] | ingestion | * | schema_drift | 1 | Columns mapped to their canonical names. |
| [OK] | business_rule | applications | unknown_sources | 0 | - |
| [OK] | business_rule | applications | orphan_applications | 0 | - |
| [OK] | ingestion | * | unknown_files | 0 | - |
| [OK] | ingestion | * | empty_files | 0 | - |
| [OK] | ingestion | * | missing_tables | 0 | - |
| [OK] | schema | requisitions | schema_requisitions | 0 | - |
| [OK] | schema | crm_activities | schema_crm_activities | 0 | - |

## Details

- **schema_drift** (1): Export files that arrived with known renamed columns. Sample: `crm_export_04.csv: activity_date->activity_at`
- **null_stage_reached** (15): Column 'stage_reached' fails check 'not_nullable'. Sample: `nan`
- **duplicate_applications** (37): Exact duplicate application rows (same values in every column). Sample: `APP-00795`, `APP-02688`, `APP-02880`, `APP-01940`, `APP-00513`
- **source_variants** (120): Source labels spelled differently from the canonical list. Sample: `occ`, `INDEED`, `OCC Mundial`, `career site`, `Careers page`
- **hired_without_offer** (9): Outcome is 'hired' but the funnel stage never reached 'hired'. Sample: `APP-02943`, `APP-01107`, `APP-00202`, `APP-01727`, `APP-01972`
- **applied_before_opening** (21): Application date earlier than the requisition's opening date. Sample: `APP-02079`, `APP-01359`, `APP-01984`, `APP-00716`, `APP-00645`
- **closed_before_opened** (6): Requisition closed before it was opened. Sample: `REQ-0027`, `REQ-0035`, `REQ-0062`, `REQ-0086`, `REQ-0088`
- **dirty_crm_keys** (250): CRM references with wrong case, extra spaces or a missing hyphen. Sample: `  APP-01004 `, `app-02359`, `APP00062`, `app-02451`, `APP00123`
- **orphan_crm_activities** (44): CRM activities whose application does not exist, even after normalization. Sample: `APP-94818`, `APP-98138`, `APP-96450`, `APP-95344`, `APP-96321`
