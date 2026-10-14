"""Controller interface. `act(env)` is called once before every env.step()."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from trafficsense.sim.env import TrafficEnv


class Controller(ABC):
    name: str

    @abstractmethod
    def act(self, env: TrafficEnv) -> None: ...

    def info(self) -> dict[str, Any]:
        """Parameters recorded in the run summary."""
        return {"name": self.name}

    def provenance(self) -> dict[str, Any]:
        """Extra provenance for summary.json (LLM controllers: model, provider, llm stats)."""
        return {}

    def write_artifacts(self, out_dir: Path) -> None:
        """Extra files in the run folder (LLM controllers: decisions.jsonl)."""
