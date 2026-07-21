"""Reader for docs/data/source_catalog.json (FIX_SPEC R3).

The single source of truth for source-system metadata. The evidence builder
gets table names and column->vertex mappings from here; the extraction SQL is
generated from the same file (scripts/generate_extraction_sql.py). No
PostgreSQL table name may appear as a literal in Python.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path("docs/data/source_catalog.json")


@lru_cache(maxsize=1)
def source_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def table_name(key: str) -> str:
    """Fully-qualified source table name for a catalog key
    (trade_details / product_hierarchy / advisor / employee)."""
    return str(source_catalog()["tables"][key]["name"])


def table_columns(key: str) -> dict[str, dict]:
    return dict(source_catalog()["tables"][key].get("columns", {}))


def scope_advisors() -> list[str]:
    return list(source_catalog().get("scope", {}).get("advisors", []))
