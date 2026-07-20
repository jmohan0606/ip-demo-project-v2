from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config.settings import get_settings
from app.models.ingestion import IngestionEntityConfig

# The registry is GENERATED from the source-of-truth foundation manifest
# (docs/tigergraph_foundation/data/manifest.json — see TIGERGRAPH_AUDIT.md), so the
# ingestion page exposes ALL vertex and edge types (60 vertices / 132 edges, 192 files),
# not a hand-picked subset. Entity names are the manifest targets with the schema
# prefix stripped (e.g. phx_dm_advisor -> "advisor", phx_dm_advisor_in_market ->
# "advisor_in_market"). Legacy hand-written names used by earlier sessions map via
# _LEGACY_ALIASES so old checkpoints/requests keep working.

_PREFIX = "phx_dm_"

_LEGACY_ALIASES: dict[str, str] = {
    "transaction": "revenue_transaction",
    "agp_goal": "goal",
    "prediction": "prediction_result",
    "feedback": "feedback_event",
    "memory": "context_memory",
}

# Larger write batches for the high-volume series files.
_BATCH_OVERRIDES: dict[str, int] = {
    "revenue_transaction": 1000,
    "monthly_product_revenue": 1000,
    "aum_in_period": 1000,
    "ncf_in_period": 1000,
    "nnm_in_period": 1000,
}


def _entity_name(target: str) -> str:
    return target[len(_PREFIX):] if target.startswith(_PREFIX) else target


@lru_cache(maxsize=1)
def _configs() -> dict[str, IngestionEntityConfig]:
    manifest_path = Path(get_settings().foundation_dir) / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    default_batch = int(manifest.get("batch_size", 500))

    configs: dict[str, IngestionEntityConfig] = {}
    for entry in manifest["files"]:
        name = _entity_name(entry["target"])
        kind = entry["kind"]
        if kind == "vertex":
            primary_key = entry["id_column"]
            required = entry.get("required_columns") or [primary_key]
        else:
            primary_key = entry["from_column"]  # display only; edges key on from->to
            required = entry.get("required_columns") or [entry["from_column"], entry["to_column"]]
        configs[name] = IngestionEntityConfig(
            entity_name=name,
            csv_file_name=entry["file"],  # includes vertices/ or edges/ subdir
            primary_key=primary_key,
            tigergraph_vertex=entry["target"],
            required_columns=list(required),
            batch_size=_BATCH_OVERRIDES.get(name, default_batch),
            kind=kind,
            order=int(entry.get("order", 0)),
            expected_rows=entry.get("expected_rows"),
            from_type=entry.get("from_type"),
            to_type=entry.get("to_type"),
            from_column=entry.get("from_column"),
            to_column=entry.get("to_column"),
        )
    return configs


def get_entity_config(entity_name: str) -> IngestionEntityConfig:
    configs = _configs()
    name = _LEGACY_ALIASES.get(entity_name, entity_name)
    try:
        return configs[name]
    except KeyError as exc:
        raise ValueError(f"Unknown ingestion entity: {entity_name}") from exc


def list_entity_configs() -> list[IngestionEntityConfig]:
    """All entities in dependency order: vertices first (manifest order), then edges."""
    configs = list(_configs().values())
    return sorted(configs, key=lambda c: (0 if c.kind == "vertex" else 1, c.order))
