from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SYNTHETIC_V23_LINEAGE_VERSION = "synthetic_v23_lineage_v1.0.0"
DATASET_VERSION = "synthetic_sft_v2.3"


@dataclass(frozen=True)
class SyntheticV23Lineage:
    generation_root_id: str
    scenario_group_id: str
    contrast_pair_group_id: str | None
    template_instance_id: str
    scenario_family_id: str
    surface_realizer_id: str
    generation_seed: int
    dataset_version: str = DATASET_VERSION

    def as_metadata(self) -> dict[str, Any]:
        return {
            "generation_root_id": self.generation_root_id,
            "scenario_group_id": self.scenario_group_id,
            "contrast_pair_group_id": self.contrast_pair_group_id,
            "template_instance_id": self.template_instance_id,
            "scenario_family_id": self.scenario_family_id,
            "surface_realizer_id": self.surface_realizer_id,
            "generation_seed": self.generation_seed,
            "dataset_version": self.dataset_version,
            "lineage_version": SYNTHETIC_V23_LINEAGE_VERSION,
        }


def leakage_keys(row: dict[str, Any]) -> dict[str, str]:
    metadata = row.get("metadata") or {}
    lineage = metadata.get("lineage") or {}
    return {
        "generation_root_id": str(lineage.get("generation_root_id") or ""),
        "scenario_group_id": str(lineage.get("scenario_group_id") or ""),
        "contrast_pair_group_id": str(lineage.get("contrast_pair_group_id") or ""),
        "template_instance_id": str(lineage.get("template_instance_id") or ""),
    }
