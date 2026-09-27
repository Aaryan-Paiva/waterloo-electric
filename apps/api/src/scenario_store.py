"""In-memory scenario store (hackathon scope). Scenarios reference a world; they never mutate it (ADR / CLAUDE.md §27)."""
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from .data.repositories import get_pack
from .projects.data_center import make_project
from .schemas.scenario import ProjectCreate, ProjectUpdate, Scenario, ScenarioCreate


class NotFound(Exception):
    pass


class ScenarioStore:
    def __init__(self) -> None:
        self._s: dict[str, Scenario] = {}
        self._lock = threading.Lock()

    def create(self, req: ScenarioCreate, parent: Optional[Scenario] = None) -> Scenario:
        pack = get_pack(req.zone_id)
        sc = Scenario(id="scn-" + uuid.uuid4().hex[:8], zone_id=req.zone_id, name=req.name or "Baseline",
                      created_at=datetime.now(timezone.utc).isoformat(), seed=req.seed if req.seed is not None else pack.der_seed,
                      projects=list(parent.projects) if parent else [], assumption_overrides=dict(parent.assumption_overrides) if parent else {},
                      parent_scenario_id=parent.id if parent else None)
        with self._lock:
            self._s[sc.id] = sc
        return sc

    def get(self, sid: str) -> Scenario:
        try:
            return self._s[sid]
        except KeyError:
            raise NotFound(sid)

    def clone(self, sid: str, name: Optional[str] = None) -> Scenario:
        src = self.get(sid)
        return self.create(ScenarioCreate(zone_id=src.zone_id, name=name or f"{src.name} (copy)", seed=src.seed), parent=src)

    def add_project(self, sid: str, req: ProjectCreate) -> Scenario:
        sc = self.get(sid)
        p = make_project("prj-" + uuid.uuid4().hex[:6], req.nominal_load_mw, req.name)
        return self._put(sc.model_copy(update={"projects": [*sc.projects, p]}))

    def update_project(self, sid: str, pid: str, req: ProjectUpdate) -> Scenario:
        sc = self.get(sid)
        if pid not in {p.id for p in sc.projects}:
            raise NotFound(pid)
        out = []
        for p in sc.projects:
            if p.id == pid:
                mw = req.nominal_load_mw if req.nominal_load_mw is not None else p.nominal_load_mw
                name = req.name if req.name is not None else (p.name if req.nominal_load_mw is None else None)
                p = make_project(p.id, mw, name)
            out.append(p)
        return self._put(sc.model_copy(update={"projects": out}))

    def delete_project(self, sid: str, pid: str) -> Scenario:
        sc = self.get(sid)
        if pid not in {p.id for p in sc.projects}:
            raise NotFound(pid)
        return self._put(sc.model_copy(update={"projects": [p for p in sc.projects if p.id != pid]}))

    def update_assumptions(self, sid: str, changes: dict) -> Scenario:
        sc = self.get(sid)
        merged = {**sc.assumption_overrides, **{k: v for k, v in changes.items() if v is not None}}
        return self._put(sc.model_copy(update={"assumption_overrides": merged}))

    def _put(self, sc: Scenario) -> Scenario:
        with self._lock:
            self._s[sc.id] = sc
        return sc

    def clear(self) -> None:
        with self._lock:
            self._s.clear()


store = ScenarioStore()
