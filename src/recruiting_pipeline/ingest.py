"""Ingestion: read raw exports, identify each table by its *content*, never overwrite sources.

Why content-based detection: export file names change (dates, prefixes, typos), but
the column signature of a table is stable. Each CSV is matched to the table whose
expected columns it overlaps most (Jaccard similarity). Known column renames are
mapped and reported as schema drift instead of failing silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import COLUMN_ALIASES, TABLE_COLUMNS
from .findings import Finding

MATCH_THRESHOLD = 0.8


@dataclass
class IngestResult:
    tables: dict[str, pd.DataFrame]
    file_map: dict[str, str]                      # file name -> table (or "unknown")
    findings: list[Finding] = field(default_factory=list)


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def identify_table(columns: list[str]) -> tuple[str, float]:
    """Return the best-matching table name and its score."""
    cols = {COLUMN_ALIASES.get(c, c) for c in columns}
    scores = {t: _jaccard(cols, set(expected)) for t, expected in TABLE_COLUMNS.items()}
    best = max(scores, key=scores.get)
    return best, scores[best]


def ingest(raw_dir: str | Path) -> IngestResult:
    raw = Path(raw_dir)
    files = sorted(raw.glob("*.csv"))
    parts: dict[str, list[pd.DataFrame]] = {t: [] for t in TABLE_COLUMNS}
    file_map: dict[str, str] = {}
    drift: list[str] = []
    unknown: list[str] = []
    empty: list[str] = []

    for path in files:
        # Read everything as text: typing happens in the schema layer, where
        # failures are counted instead of being coerced away silently.
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        table, score = identify_table(list(df.columns))
        if score < MATCH_THRESHOLD:
            file_map[path.name] = "unknown"
            unknown.append(path.name)
            continue
        renamed = {c: COLUMN_ALIASES[c] for c in df.columns if c in COLUMN_ALIASES}
        if renamed:
            drift.append(f"{path.name}: " + ", ".join(f"{o}->{n}" for o, n in renamed.items()))
            df = df.rename(columns=renamed)
        if df.empty:
            empty.append(path.name)
        file_map[path.name] = table
        df["_source_file"] = path.name           # lineage: every row knows its origin
        parts[table].append(df)

    tables = {
        t: (pd.concat(p, ignore_index=True) if p
            else pd.DataFrame(columns=TABLE_COLUMNS[t] + ["_source_file"]))
        for t, p in parts.items()
    }
    missing = [t for t, p in parts.items() if not p]

    findings = [
        Finding("schema_drift", "*", "ingestion", "WARN", len(drift),
                "Export files that arrived with known renamed columns.",
                "Columns mapped to their canonical names.", drift[:5]),
        Finding("unknown_files", "*", "ingestion", "ERROR", len(unknown),
                f"CSV files that match no table (Jaccard < {MATCH_THRESHOLD}).",
                "File ignored; review the export.", unknown[:5]),
        Finding("empty_files", "*", "ingestion", "ERROR", len(empty),
                "Recognized export files with zero rows.",
                "Check the export job.", empty[:5]),
        Finding("missing_tables", "*", "ingestion", "ERROR", len(missing),
                "Expected tables with no source file at all.",
                "Pipeline cannot compute KPIs that depend on them.", missing),
    ]
    return IngestResult(tables=tables, file_map=file_map, findings=findings)
