"""Simulation clock (CLAUDE.md §16.1). Playback speeds are simulated hours advanced per real second."""
from dataclasses import dataclass

SPEEDS = {"1x": 1, "10x": 10, "100x": 100, "1000x": 1000}


@dataclass
class SimulationClock:
    n_hours: int
    index: int = 0

    def advance(self, real_seconds: float, speed: str = "1x") -> int:
        self.index = min(self.n_hours - 1, self.index + int(real_seconds * SPEEDS[speed]))
        return self.index

    def seek(self, index: int) -> int:
        self.index = max(0, min(self.n_hours - 1, index))
        return self.index
