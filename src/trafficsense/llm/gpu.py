"""GPU checks for LLM runs (nvidia-smi): the LLM must have the GPU to itself (CLAUDE.md:
the LLM and YOLO never share it). free_gpu() unloads every Ollama model and then requires an
idle GPU; VramSampler records memory.used during a run."""
from __future__ import annotations

import subprocess
import threading
import time

from trafficsense.llm.client import OllamaClient

GPU_IDLE_MAX_MIB = 300


def gpu_used_mib() -> int:
    out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                  text=True)
    vals = [int(x) for x in out.split()]
    if len(vals) != 1:
        raise SystemExit(f"Expected one GPU, nvidia-smi reports {len(vals)}")
    return vals[0]


def gpu_name() -> str:
    return subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                                   text=True).strip()


def free_gpu(client: OllamaClient) -> int:
    """Unload every Ollama model, then require an idle GPU. Returns the idle memory.used (MiB)."""
    for m in client.loaded_models():
        client.unload(m["name"])
    for _ in range(30):
        if not client.loaded_models():
            break
        time.sleep(1)
    else:
        raise SystemExit(f"Ollama still has models loaded: {[m['name'] for m in client.loaded_models()]}")
    time.sleep(3)
    used = gpu_used_mib()
    if used > GPU_IDLE_MAX_MIB:
        raise SystemExit(f"GPU not free: {used} MiB in use with no Ollama model loaded (limit {GPU_IDLE_MAX_MIB}). "
                         "Stop other GPU work (YOLO, other servers) first.")
    return used


class VramSampler(threading.Thread):
    def __init__(self, period_s: float = 1.0):
        super().__init__(daemon=True)
        self.period, self.samples, self._halt = period_s, [], threading.Event()

    def run(self):
        while not self._halt.is_set():
            self.samples.append(gpu_used_mib())
            self._halt.wait(self.period)

    def stop(self) -> list[int]:
        self._halt.set()
        self.join()
        return self.samples
