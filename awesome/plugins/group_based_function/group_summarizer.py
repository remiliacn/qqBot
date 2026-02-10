from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    ok: bool
    summary: str
