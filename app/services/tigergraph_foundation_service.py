from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config.settings import get_settings

SCHEMA_PREFIX_V2 = "phx_dm_v2_"


class TigerGraphFoundationService:
    """Reports on the V2 TigerGraph foundation package
    (docs/tigergraph_foundation/tigergraph/{schema,queries,loading})."""

    def __init__(self) -> None:
        self.root = Path(get_settings().foundation_dir) / "tigergraph"

    def list_schema_files(self) -> list[str]:
        d = self.root / "schema"
        return sorted(p.name for p in d.glob("*.gsql")) if d.is_dir() else []

    def list_query_files(self) -> list[str]:
        d = self.root / "queries"
        return sorted(p.name for p in d.glob("*.gsql")) if d.is_dir() else []

    def query_catalog(self) -> dict[str, Any]:
        path = self.root / "queries" / "query_catalog.json"
        if not path.is_file():
            return {"queries": []}
        return json.loads(path.read_text())

    def get_schema_inventory(self) -> dict[str, Any]:
        """Parse vertex/edge names out of the schema DDL files."""
        vertices: list[str] = []
        edges: list[str] = []
        d = self.root / "schema"
        if d.is_dir():
            for f in sorted(d.glob("*.gsql")):
                for line in f.read_text().splitlines():
                    s = line.strip()
                    up = s.upper()
                    if up.startswith("CREATE VERTEX"):
                        vertices.append(s.split()[2].split("(")[0])
                    elif up.startswith(("CREATE DIRECTED EDGE", "CREATE UNDIRECTED EDGE")):
                        edges.append(s.split()[3].split("(")[0])
        return {
            "vertex_count": len(vertices),
            "edge_count": len(edges),
            "vertices": vertices,
            "edges": edges,
            "schema_files": self.list_schema_files(),
            "query_files": self.list_query_files(),
        }

    def validate_prefix_convention(self) -> dict[str, Any]:
        inv = self.get_schema_inventory()
        bad = [n for n in inv["vertices"] + inv["edges"] if not n.startswith(SCHEMA_PREFIX_V2)]
        return {"prefix": SCHEMA_PREFIX_V2, "compliant": not bad, "violations": bad}
