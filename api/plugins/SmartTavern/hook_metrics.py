"""Hook 执行指标收集器。"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class HookCallMetrics:
    call_count: int = 0
    total_time_ms: float = 0.0
    error_count: int = 0
    last_called: float = 0.0


class MetricsCollector:
    """按 strategy_id × hook_name 收集调用指标。"""

    def __init__(self):
        self._metrics: dict[str, dict[str, HookCallMetrics]] = defaultdict(lambda: defaultdict(HookCallMetrics))

    def record(self, strategy_id: str, hook_name: str, duration_ms: float, *, error: bool = False):
        m = self._metrics[strategy_id][hook_name]
        m.call_count += 1
        m.total_time_ms += duration_ms
        if error:
            m.error_count += 1
        m.last_called = time.time()

    def snapshot(self) -> dict:
        out: dict[str, dict[str, dict]] = {}
        for sid, hooks in self._metrics.items():
            out[sid] = {}
            for hname, m in hooks.items():
                out[sid][hname] = {
                    "call_count": m.call_count,
                    "total_time_ms": round(m.total_time_ms, 2),
                    "avg_time_ms": round(m.total_time_ms / m.call_count, 2) if m.call_count else 0,
                    "error_count": m.error_count,
                    "last_called": m.last_called,
                }
        return out

    def remove_strategy(self, strategy_id: str):
        self._metrics.pop(strategy_id, None)

    def reset(self):
        self._metrics.clear()
