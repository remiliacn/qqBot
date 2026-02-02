from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class WebSearchPrejudgeResult:
    decision: Literal["yes", "no", "uncertain"]
    query: str
    reason: str
