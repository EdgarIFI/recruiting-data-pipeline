# recruiting-data-pipeline

> **Status: work in progress.** This first milestone covers synthetic data generation, ingestion and validation. The SQL model, hiring-funnel KPIs, dashboard and the full write-up come next.

A recruiting team needs one reliable view of its hiring funnel: where candidates come from, where they drop out, and how long requisitions take to fill. In practice that data lives in several systems that disagree with each other. This project builds the pipeline that makes those systems trustworthy before any KPI is computed.

**All data in this repository is synthetic.** Clients, candidates and figures are invented by a seeded generator.

## What works today

1. **Synthetic exports with known defects.** `generate` writes an applicant-tracking export, a requisitions export and six periodic CRM exports. It injects eight kinds of data-quality issues into disjoint rows and records their exact counts in a manifest.
2. **Content-based ingestion.** Each CSV is matched to a table by its columns (Jaccard similarity), not by its file name. Known column renames are mapped and reported as schema drift. Source files are never modified, and every row keeps its file of origin.
3. **Two-layer validation.**
   - *Schema* ([pandera](https://pandera.readthedocs.io)): types, formats, nullability and allowed values.
   - *Business rules* (written by hand): duplicates, source spelling variants, funnel consistency, date logic across tables, and CRM references that point nowhere.
   - Every check reports **[OK] / [WARN] / [ERROR]**, the number of affected rows, and what the pipeline does about them.
4. **Tests against ground truth.** Validation must find *exactly* the injected count of every issue, for any seed, and *zero* issues on a clean dataset.

## Quickstart

```bash
pip install -e ".[dev]"
recruiting-pipeline generate --out data/raw --seed 2027
recruiting-pipeline validate --raw data/raw --reports reports
pytest
```

`reports/validation_report.md` contains the human-readable report; `validation_report.json` contains the machine-readable one.

## Project layout

```
src/recruiting_pipeline/
  config.py      data contract: columns, categories, sizes, injected issues
  generate.py    seeded synthetic generator + ground-truth manifest
  ingest.py      content-based table detection, schema-drift mapping, lineage
  schemas.py     pandera schemas (column-level checks)
  rules.py       business rules (cross-field and cross-table checks)
  normalize.py   shared normalization (what validation counts as fixable is what cleaning fixes)
  validate.py    orchestration and report
tests/           ground-truth tests, clean-data test, ingestion tests
```

## About this project

Code and documentation developed with AI assistance (Claude); problem framing, design decisions and validation are my own.

License: MIT.
