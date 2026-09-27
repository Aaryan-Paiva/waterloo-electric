"""Bounded in-memory store of agentic runs (persistence can replace it behind the same interface). Holds what is needed to inspect and
replay a run: the public AgenticRun, the recorded owner actions, and the inputs."""
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from ..schemas.owners import AgenticRun

MAX_RUNS = 50


@dataclass
class StoredRun:
    run: AgenticRun
    actions: dict[str, list]           # owner_id -> [first action, optional revision]
    window_start: str
    window_end: str
    window_id: Optional[str]
    incentive: float
    tail_hours: int


class RunStore:
    def __init__(self) -> None:
        self._r: "OrderedDict[str, StoredRun]" = OrderedDict()
        self._lock = threading.Lock()

    def put(self, s: StoredRun) -> None:
        with self._lock:
            self._r[s.run.id] = s
            while len(self._r) > MAX_RUNS:
                self._r.popitem(last=False)

    def get(self, rid: str) -> Optional[StoredRun]:
        with self._lock:
            return self._r.get(rid)

    def clear(self) -> None:
        with self._lock:
            self._r.clear()


runs = RunStore()
