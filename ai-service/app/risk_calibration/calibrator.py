from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


class ConfidenceCalibrator(Protocol):
    method: str
    version: str

    def predict(self, value: float) -> float: ...
    def to_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class PlattCalibrator:
    slope: float
    intercept: float
    version: str = "confidence-calibrator-v1"
    method: str = "platt"

    def predict(self, value: float) -> float:
        z = max(-35.0, min(35.0, self.slope * clamp(value) + self.intercept))
        return 1.0 / (1.0 + math.exp(-z))

    def to_dict(self) -> dict[str, object]:
        return {"version": self.version, "method": self.method, "slope": self.slope, "intercept": self.intercept}


@dataclass(frozen=True)
class IsotonicCalibrator:
    thresholds: tuple[float, ...]
    values: tuple[float, ...]
    version: str = "confidence-calibrator-v1"
    method: str = "isotonic"

    def predict(self, value: float) -> float:
        x = clamp(value)
        for threshold, calibrated in zip(self.thresholds, self.values):
            if x <= threshold:
                return clamp(calibrated)
        return clamp(self.values[-1] if self.values else x)

    def to_dict(self) -> dict[str, object]:
        return {"version": self.version, "method": self.method, "thresholds": list(self.thresholds), "values": list(self.values)}


def fit_platt(confidences: list[float], labels: list[int]) -> PlattCalibrator:
    if not confidences or len(confidences) != len(labels):
        raise ValueError("CALIBRATION_DATA_INVALID")
    slope, intercept = 1.0, 0.0
    learning_rate = 0.15
    regularization = 0.002
    size = float(len(confidences))
    for _ in range(4000):
        grad_slope = regularization * slope
        grad_intercept = 0.0
        for confidence, label in zip(confidences, labels):
            z = max(-35.0, min(35.0, slope * clamp(confidence) + intercept))
            prediction = 1.0 / (1.0 + math.exp(-z))
            error = prediction - int(label)
            grad_slope += error * confidence / size
            grad_intercept += error / size
        slope -= learning_rate * grad_slope
        intercept -= learning_rate * grad_intercept
    return PlattCalibrator(slope=slope, intercept=intercept)


def fit_isotonic(confidences: list[float], labels: list[int]) -> IsotonicCalibrator:
    if not confidences or len(confidences) != len(labels):
        raise ValueError("CALIBRATION_DATA_INVALID")
    grouped: list[list[float]] = []
    for confidence, label in sorted(zip(confidences, labels), key=lambda item: item[0]):
        x = clamp(confidence)
        if grouped and grouped[-1][1] == x:
            grouped[-1][2] += float(label)
            grouped[-1][3] += 1.0
        else:
            grouped.append([x, x, float(label), 1.0])
    blocks = grouped
    index = 0
    while index < len(blocks) - 1:
        left = blocks[index][2] / blocks[index][3]
        right = blocks[index + 1][2] / blocks[index + 1][3]
        if left <= right:
            index += 1
            continue
        blocks[index:index + 2] = [[blocks[index][0], blocks[index + 1][1], blocks[index][2] + blocks[index + 1][2], blocks[index][3] + blocks[index + 1][3]]]
        index = max(0, index - 1)
    return IsotonicCalibrator(
        thresholds=tuple(block[1] for block in blocks),
        values=tuple(block[2] / block[3] for block in blocks),
    )


def load_calibrator(path: str | Path) -> ConfidenceCalibrator | None:
    artifact = Path(path)
    if not artifact.exists():
        return None
    data = json.loads(artifact.read_text(encoding="utf-8"))
    if data.get("method") == "platt":
        return PlattCalibrator(float(data["slope"]), float(data["intercept"]), str(data.get("version") or "confidence-calibrator-v1"))
    if data.get("method") == "isotonic":
        return IsotonicCalibrator(
            tuple(float(item) for item in data.get("thresholds", [])),
            tuple(float(item) for item in data.get("values", [])),
            str(data.get("version") or "confidence-calibrator-v1"),
        )
    raise ValueError("CALIBRATOR_METHOD_UNSUPPORTED")


def save_calibrator(calibrator: ConfidenceCalibrator, path: str | Path, metadata: dict[str, object] | None = None) -> None:
    artifact = Path(path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    payload = {**calibrator.to_dict(), "metadata": metadata or {}}
    artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def calibration_metrics(confidences: list[float], labels: list[int], bins: int = 10) -> dict[str, object]:
    if not confidences or len(confidences) != len(labels):
        return {"ece": 0.0, "brier": 0.0, "reliability": []}
    rows = []
    ece = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        positions = [i for i, value in enumerate(confidences) if lower <= value < upper or (index == bins - 1 and value == 1.0)]
        if not positions:
            rows.append({"bucket": f"{lower:.1f}-{upper:.1f}", "count": 0, "averageConfidence": None, "accuracy": None})
            continue
        average = sum(confidences[i] for i in positions) / len(positions)
        accuracy = sum(labels[i] for i in positions) / len(positions)
        ece += len(positions) / len(confidences) * abs(accuracy - average)
        rows.append({"bucket": f"{lower:.1f}-{upper:.1f}", "count": len(positions), "averageConfidence": round(average, 6), "accuracy": round(accuracy, 6)})
    brier = sum((confidence - label) ** 2 for confidence, label in zip(confidences, labels)) / len(confidences)
    return {"ece": round(ece, 6), "brier": round(brier, 6), "reliability": rows}
