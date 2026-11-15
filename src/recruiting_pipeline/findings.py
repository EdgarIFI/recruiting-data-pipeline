"""A single, uniform record for every check the pipeline runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SEVERITY_ORDER = {"OK": 0, "INFO": 1, "WARN": 2, "ERROR": 3}


@dataclass
class Finding:
    """Result of one check.

    severity: what it means if count > 0.
      WARN  -> the pipeline can fix it automatically (and says how).
      ERROR -> the rows cannot be trusted; they are excluded from KPIs and flagged.
    status: OK when count == 0, otherwise the severity.
    """

    check_id: str
    table: str
    layer: str          # "ingestion", "schema" or "business_rule"
    severity: str
    count: int
    description: str
    action: str = ""
    sample: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "OK" if self.count == 0 else self.severity

    def to_dict(self) -> dict:
        return {**asdict(self), "status": self.status}
