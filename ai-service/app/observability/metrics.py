from __future__ import annotations

from collections import defaultdict
from statistics import mean


class MetricsRegistry:
    def __init__(self):
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = defaultdict(float)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def observe(self, name: str, value: float) -> None:
        self.histograms[name].append(value)

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def reset(self) -> None:
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "histograms": {key: self._histogram(values) for key, values in self.histograms.items()},
            "gauges": dict(self.gauges),
        }

    @staticmethod
    def _histogram(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0}
        ordered = sorted(values)
        return {
            "count": len(values),
            "min": round(ordered[0], 4),
            "max": round(ordered[-1], 4),
            "avg": round(mean(values), 4),
            "p50": round(percentile(ordered, 0.50), 4),
            "p95": round(percentile(ordered, 0.95), 4),
        }


def percentile(ordered_values: list[float], p: float) -> float:
    if not ordered_values:
        return 0
    index = min(len(ordered_values) - 1, int(round((len(ordered_values) - 1) * p)))
    return ordered_values[index]


metrics_registry = MetricsRegistry()
