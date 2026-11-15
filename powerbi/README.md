# Power BI layer: build guide

The interactive layer of this project, built in Power BI Desktop on top of the model the pipeline exports. It is saved as a **Power BI Project (PBIP)**, so the report and the semantic model are plain-text files that Git can diff and review.

**Rule of this layer:** every number in the report must match the SQL KPIs in [`docs/kpis`](../docs/kpis). The DAX measures below are a third, independent implementation of the same definitions (after SQL and pandas), and the [reconciliation table](#6-reconcile-with-the-sql-kpis) is how that is checked.

---

## 0. Prerequisites

- Windows with **Power BI Desktop** (free, from the Microsoft Store) and **Git**.
- No Python needed: the model tables are committed in [`docs/bi`](../docs/bi), produced by `recruiting-pipeline run --out docs --bi`.

```bash
# Clone to a neutral path: the data-folder path is saved inside the project files,
# so a path without your Windows user name keeps it out of the repository.
git clone https://github.com/EdgarIFI/recruiting-data-pipeline.git C:/dev/recruiting-data-pipeline
cd C:/dev/recruiting-data-pipeline

# Commit with your GitHub no-reply address, not a personal email
# (find it in GitHub → Settings → Emails → "Keep my email addresses private")
git config user.email "<your-id>+<your-user>@users.noreply.github.com"

git checkout -b feat/powerbi-layer
```

## 1. Data: the tables and their grain

| File in `docs/bi/` | Grain | Key columns |
|---|---|---|
| `dim_requisition.csv` | one row per requisition | `req_id`, `status`, `seniority`, `time_to_fill_days`, `ttf_eligible` |
| `fact_application.csv` | one row per unique application | `application_id`, `req_id`, `source`, `stage_rank`, `outcome`, `kpi_eligible` |
| `fact_crm_activity.csv` | one row per CRM activity | `activity_id`, `application_id`, `activity_type`, `kpi_eligible` |
| `dim_stage.csv` | one row per funnel stage | `stage`, `stage_rank` (0 = applied … 4 = hired) |
| `dq_log.csv` | one row per (entity, data-quality check) | `table_name`, `entity_id`, `check_id`, `severity`, `action` |
| `params.csv` | one row | `as_of` (snapshot date) |

## 2. Power Query: load with explicit types

1. **Home → Transform data → Manage parameters → New:** name `DataFolder`, type Text, value `C:\dev\recruiting-data-pipeline\docs\bi\` (with the trailing backslash).
2. For each table: **New source → Blank query → Advanced editor**, paste the query, and rename it to the file name without `.csv`.

> **Alternative source.** Pointing `DataFolder` to `https://raw.githubusercontent.com/EdgarIFI/recruiting-data-pipeline/main/docs/bi/` and replacing `File.Contents` with `Web.Contents` lets anyone refresh the report without cloning. The cost: the report then reads `main`, not the commit you have checked out. The local folder is the default here because the report should always match the code next to it.

Every query has the same shape. Types are set explicitly with the `en-US` culture, so dates and booleans parse the same on any Windows locale:

```powerquery
let
    Source  = Csv.Document(File.Contents(DataFolder & "fact_application.csv"),
                           [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"application_id", type text}, {"candidate_id", type text}, {"req_id", type text},
        {"source", type text}, {"source_raw", type text}, {"applied_at", type date},
        {"stage_reached", type text}, {"stage_rank", Int64.Type}, {"outcome", type text},
        {"kpi_eligible", type logical}}, "en-US")
in
    Typed
```

Type lists for the other tables (replace the file name and the list):

```powerquery
// dim_requisition.csv
{{"req_id", type text}, {"client", type text}, {"area", type text}, {"city", type text},
 {"seniority", type text}, {"openings", Int64.Type}, {"opened_at", type date}, {"closed_at", type date},
 {"status", type text}, {"recruiter_id", type text}, {"time_to_fill_days", Int64.Type},
 {"ttf_eligible", type logical}, {"dq_closed_before_opened", type logical}}

// fact_crm_activity.csv
{{"activity_id", type text}, {"application_id", type text}, {"activity_type", type text},
 {"activity_at", type date}, {"recruiter_id", type text}, {"kpi_eligible", type logical}}

// dim_stage.csv
{{"stage", type text}, {"stage_rank", Int64.Type}}

// dq_log.csv
{{"table_name", type text}, {"entity_id", type text}, {"check_id", type text},
 {"severity", type text}, {"action", type text}}

// params.csv
{{"as_of", type date}}
```

**Check before closing Power Query:** row counts must be `dim_requisition` 120, `fact_application` 3,000, `fact_crm_activity` 6,000, `dim_stage` 5, `dq_log` 502, `params` 1.

## 3. Model: relationships

| From (many) | To (one) | Cardinality | Filter direction |
|---|---|---|---|
| `fact_application[req_id]` | `dim_requisition[req_id]` | many-to-one | single |
| `fact_crm_activity[application_id]` | `fact_application[application_id]` | many-to-one | single |

**Deliberately not related:** `dim_stage`, `dq_log` and `params`.

- **`dim_stage`:** "reached a stage" is cumulative (`stage_rank >= r`), not equality. A relationship would filter each stage to the applications that *stopped* there, which is a different and misleading number. The funnel measures read the selected stage instead.
- **`dq_log`:** it mixes entities from three tables in one column.
- **`params`:** a single value.

**Sort orders** (Column tools → Sort by column):
- `dim_stage[stage]` by `dim_stage[stage_rank]`;
- `Seniority Order` and `Aging Bucket Order` (below) for their label columns.

## 4. Calculated columns (on `dim_requisition`)

```dax
Days Open =
IF ( dim_requisition[status] = "open",
     DATEDIFF ( dim_requisition[opened_at], MAX ( params[as_of] ), DAY ) )

Aging Bucket =
SWITCH ( TRUE (),
    ISBLANK ( dim_requisition[Days Open] ), BLANK (),
    dim_requisition[Days Open] <= 30, "0-30 days",
    dim_requisition[Days Open] <= 60, "31-60 days",
    dim_requisition[Days Open] <= 90, "61-90 days",
    "90+ days" )

Aging Bucket Order =
SWITCH ( dim_requisition[Aging Bucket],
    "0-30 days", 1, "31-60 days", 2, "61-90 days", 3, "90+ days", 4 )

Seniority Order =
SWITCH ( dim_requisition[seniority], "Junior", 1, "Mid", 2, "Senior", 3 )
```

## 5. Measures

Keep them in one place: **Home → Enter data**, name the table `_Measures`, Load. Once the first measure is in it, delete its default `Column1`; Power BI then shows it as a measure table at the top of the Data pane. Each measure mirrors one SQL file in `src/recruiting_pipeline/sql/`.

```dax
// ---- volumes (only rows that passed validation) ----
Applications (eligible) =
CALCULATE ( COUNTROWS ( fact_application ), fact_application[kpi_eligible] = TRUE () )

Applications (filled reqs) =
CALCULATE ( [Applications (eligible)], dim_requisition[status] = "filled" )

Reached Interview (filled reqs) =
CALCULATE ( [Applications (filled reqs)], fact_application[stage_rank] >= 2 )

Hires (filled reqs) =
CALCULATE ( [Applications (filled reqs)], fact_application[outcome] = "hired" )

// ---- rates (kpi_source_effectiveness.sql) ----
Interview Rate = DIVIDE ( [Reached Interview (filled reqs)], [Applications (filled reqs)] )
Hire Rate      = DIVIDE ( [Hires (filled reqs)], [Applications (filled reqs)] )

// 95% Wilson score interval, same formula as the SQL macros wilson_low / wilson_high
Interview Rate Low =
VAR k = [Reached Interview (filled reqs)]
VAR n = [Applications (filled reqs)]
VAR z = 1.96
VAR p = DIVIDE ( k, n )
RETURN IF ( n > 0,
    ( p + z ^ 2 / ( 2 * n ) - z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ) ) / ( 1 + z ^ 2 / n ) )

Interview Rate High =
VAR k = [Reached Interview (filled reqs)]
VAR n = [Applications (filled reqs)]
VAR z = 1.96
VAR p = DIVIDE ( k, n )
RETURN IF ( n > 0,
    ( p + z ^ 2 / ( 2 * n ) + z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ) ) / ( 1 + z ^ 2 / n ) )

// ---- funnel (kpi_funnel.sql, cohort = filled requisitions) ----
Reached Stage =
VAR r = SELECTEDVALUE ( dim_stage[stage_rank] )
RETURN CALCULATE ( [Applications (filled reqs)], fact_application[stage_rank] >= r )

Share of Applicants = DIVIDE ( [Reached Stage], [Applications (filled reqs)] )

Conversion from Previous =
VAR r = SELECTEDVALUE ( dim_stage[stage_rank] )
VAR prev = CALCULATE ( [Applications (filled reqs)], fact_application[stage_rank] >= r - 1 )
RETURN IF ( r > 0, DIVIDE ( [Reached Stage], prev ) )

// ---- time-to-fill (kpi_time_to_fill.sql); PERCENTILE.INC = QUANTILE_CONT ----
Median TTF (days) =
CALCULATE ( MEDIAN ( dim_requisition[time_to_fill_days] ), dim_requisition[ttf_eligible] = TRUE () )

TTF P25 (days) =
CALCULATE ( PERCENTILE.INC ( dim_requisition[time_to_fill_days], 0.25 ), dim_requisition[ttf_eligible] = TRUE () )

TTF P75 (days) =
CALCULATE ( PERCENTILE.INC ( dim_requisition[time_to_fill_days], 0.75 ), dim_requisition[ttf_eligible] = TRUE () )

// ---- backlog (kpi_open_requisition_aging.sql) ----
Open Requisitions = CALCULATE ( COUNTROWS ( dim_requisition ), dim_requisition[status] = "open" )

Open Requisitions > 90 days =
CALCULATE ( [Open Requisitions], dim_requisition[Aging Bucket] = "90+ days" )

// ---- data quality (kpi_data_quality.sql) ----
Affected Rows = COUNTROWS ( dq_log )
```

Formats: rates as percentage with 1 decimal; days as whole numbers.

## 6. Reconcile with the SQL KPIs

Before designing any page, put each measure in a card or table and check it against these values from `docs/kpis` (default run, seed 2027). **Every row must match.** If one doesn't, the DAX is wrong, not the SQL: it has two independent checks already.

| Measure | Filter | Expected | Source file |
|---|---|---:|---|
| Applications (filled reqs) | – | 1,546 | `funnel.csv` |
| Reached Stage | screening / interview / offer / hired | 980 / 573 / 259 / 106 | `funnel.csv` |
| Conversion from Previous | screening / interview / offer / hired | 63.4% / 58.5% / 45.2% / 40.9% | `funnel.csv` |
| Interview Rate | – | 37.1% | `funnel.csv` |
| Hire Rate | – | 6.9% | `funnel.csv` |
| Interview Rate (Low–High) | source = Referral | 52.6% (45.6%–59.5%) | `source_effectiveness.csv` |
| Applications (filled reqs) | source = LinkedIn | 507 | `source_effectiveness.csv` |
| Median TTF (days) | – | 41 (P25 31, P75 50) | `time_to_fill.csv` |
| Median TTF (days) | Junior / Mid / Senior | 35.5 / 45 / 68 | `time_to_fill.csv` |
| Open Requisitions | – | 42 | `open_requisition_aging.csv` |
| Open Requisitions | by Aging Bucket | 8 / 9 / 10 / 15 | `open_requisition_aging.csv` |
| Affected Rows | by check_id | 250, 120, 44, 37, 21, 15, 9, 6 | `data_quality.csv` |

## 7. Report pages

Apply the theme first: **View → Themes → Browse for themes → `powerbi/theme.json`**.

| Page | Visuals | Message |
|---|---|---|
| **1. Overview** | Cards: Applications (filled reqs), Interview Rate, Hire Rate, Median TTF, Open Requisitions > 90 days. Bar chart: `dim_stage[stage]` × Reached Stage, tooltip Conversion from Previous. Text: "All data is synthetic." | The funnel at a glance |
| **2. Sources** | Bar chart: `source` × Interview Rate, sorted descending. Table: source, Applications (filled reqs), Interview Rate, Low, High, Hire Rate. Slicers: city, area | Referrals stand out; watch the intervals widen as filters shrink n |
| **3. Time-to-fill & backlog** | Column chart: seniority × Median TTF. Column chart: Aging Bucket × Open Requisitions. Text: time-to-fill is right-censored (open requisitions are not in it) | Senior roles take longest (n = 9, read with care); more than a third of the backlog (15 of 42) is over 90 days old |
| **4. Data quality** | Bar chart: `check_id` × Affected Rows, legend `severity`. Table: table_name, entity_id, check_id, action | What was fixed (WARN) and what was excluded (ERROR) |

## 8. Save, export, publish

1. **File → Save as → Power BI project files (\*.pbip)** → `powerbi/RecruitingFunnel.pbip`. This creates `RecruitingFunnel.Report/` and `RecruitingFunnel.SemanticModel/` next to it. If the option is missing in your version, enable it under File → Options → Preview features.
2. **File → Export → Export to PDF** → `docs/powerbi/recruiting-funnel.pdf`. Also save one screenshot per page as `docs/powerbi/page-1.png` … `page-4.png`.
3. Commit and push:
   ```bash
   git add powerbi docs/powerbi
   git commit -m "Add Power BI layer (PBIP) on the exported model"
   git push -u origin feat/powerbi-layer
   ```
4. Open the pull request on GitHub. The measures and relationships appear as readable text (TMDL) in "Files changed", which makes the review possible.

`.pbi/localSettings.json` and `.pbi/cache.abf` are ignored on purpose: they are local cache and user settings, not part of the project.
