from dataclasses import dataclass
from time import monotonic


@dataclass
class GroupSummaryState:
    summary: str
    last_update_ts: float
    turns_since_update: int


class GroupSummaryStore:
    def __init__(self) -> None:
        self._by_group: dict[str, GroupSummaryState] = {}

    def get_summary(self, group_id: str) -> str:
        state = self._by_group.get(str(group_id))
        if state is None:
            return ''
        return state.summary

    def record_turn(self, group_id: str) -> None:
        key = str(group_id)
        state = self._by_group.get(key)
        if state is None:
            self._by_group[key] = GroupSummaryState(summary='', last_update_ts=monotonic(), turns_since_update=1)
            return
        state.turns_since_update += 1

    def set_summary(self, group_id: str, summary: str) -> None:
        self._by_group[str(group_id)] = GroupSummaryState(
            summary=summary.strip(),
            last_update_ts=monotonic(),
            turns_since_update=0,
        )

    def turns_since_update(self, group_id: str) -> int:
        state = self._by_group.get(str(group_id))
        if state is None:
            return 0
        return state.turns_since_update


group_summary_store = GroupSummaryStore()
