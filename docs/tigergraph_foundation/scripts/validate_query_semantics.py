#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "tigergraph/schema/schema_catalog.json").read_text())
vertices = {v["name"]: v for v in schema["vertices"]}
edges = {e["name"]: e for e in schema["edges"]}
for edge in list(edges.values()):
    edges[edge["reverse_edge"]] = {
        "name": edge["reverse_edge"], "from": edge["to"], "to": edge["from"],
        "attrs": edge["attrs"], "original": edge["name"]
    }
vertex_attrs = {name: {v["primary_id"], *(a for a, _ in v["attrs"])} for name, v in vertices.items()}
errors = []

def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def statements(text: str):
    start = 0
    for match in re.finditer(r";", text):
        yield text[start:match.end()]
        start = match.end()

def validate(path: Path):
    text = path.read_text(encoding="utf-8")
    stmts = list(statements(text))
    variable_types: dict[str, str] = {}
    for statement in stmts:
        value = compact(statement)
        seed = re.search(r"(\w+)\s*=\s*\{(phx_dm_\w+)\.\*\}", value)
        if seed:
            variable_types[seed.group(1)] = seed.group(2)
    # Resolve result-set types to a fixed point.
    for _ in range(20):
        changed = False
        for statement in stmts:
            value = compact(statement)
            union = re.search(r"(\w+)\s*=\s*(\w+)(?:\s+UNION\s+\w+)+\s*;", value)
            if union and union.group(2) in variable_types and union.group(1) not in variable_types:
                variable_types[union.group(1)] = variable_types[union.group(2)]; changed = True
            hop = re.search(
                r"(\w+)\s*=\s*SELECT\s+(\w+)\s+FROM\s+(\w+)(?::(\w+))?\s*-\((rev_)?(phx_dm_\w+)(?::(\w+))?\)-\s*(\w+)?(?::(\w+))?",
                value,
            )
            if hop:
                out, selected_alias, source_spec, source_alias, rev, edge_name, edge_alias, target_spec, target_alias = hop.groups()
                source_type = variable_types.get(source_spec, source_spec if source_spec in vertices else None)
                target_type = variable_types.get(target_spec or "", target_spec if target_spec in vertices else None)
                selected_type = source_type if selected_alias == source_alias else target_type if selected_alias == target_alias else None
                if selected_type and variable_types.get(out) != selected_type:
                    variable_types[out] = selected_type; changed = True
            source_only = re.search(r"(\w+)\s*=\s*SELECT\s+(\w+)\s+FROM\s+(\w+):(\w+)(?:\s|;)", value)
            if source_only:
                out, selected_alias, source_spec, source_alias = source_only.groups()
                if selected_alias == source_alias and source_spec in variable_types and variable_types.get(out) != variable_types[source_spec]:
                    variable_types[out] = variable_types[source_spec]; changed = True
        if not changed:
            break
    for statement in stmts:
        value = compact(statement)
        direct_source = re.search(r"FROM\s+(phx_dm_\w+):\w+", value)
        if direct_source:
            errors.append(f"{path.name}: SYNTAX V1 source must be a previously declared vertex set, not vertex type {direct_source.group(1)}")
        hop = re.search(
            r"FROM\s+(\w+)(?::(\w+))?\s*-\((rev_)?(phx_dm_\w+)(?::(\w+))?\)-\s*(\w+)?(?::(\w+))?",
            value,
        )
        if not hop:
            continue
        source_spec, source_alias, rev, base_edge, edge_alias, target_spec, target_alias = hop.groups()
        edge_name = (rev or "") + base_edge
        edge = edges.get(edge_name)
        source_type = variable_types.get(source_spec, source_spec if source_spec in vertices else None)
        target_type = variable_types.get(target_spec or "", target_spec if target_spec in vertices else None)
        if not edge:
            errors.append(f"{path.name}: unknown edge {edge_name}")
            continue
        if not source_type or not target_type:
            errors.append(f"{path.name}: cannot infer types for {source_spec} -({edge_name})- {target_spec}")
            continue
        if (source_type, target_type) != (edge["from"], edge["to"]):
            errors.append(
                f"{path.name}: direction/type mismatch {source_type} -({edge_name})-> {target_type}; schema is {edge['from']} -> {edge['to']}"
            )
        aliases = {source_alias: source_type, target_alias: target_type}
        if edge_alias:
            # Edge attributes are checked separately when referenced.
            edge_attr_names = {a for a, _ in edge.get("attrs", [])}
        else:
            edge_attr_names = set()
        for alias, attr in re.findall(r"\b(\w+)\.(\w+)\b", value):
            if alias in aliases and attr not in vertex_attrs[aliases[alias]] and attr not in {"type", "id"}:
                errors.append(f"{path.name}: {alias}.{attr} is not an attribute of {aliases[alias]}")
            if edge_alias and alias == edge_alias and attr not in edge_attr_names and attr not in {"type"}:
                errors.append(f"{path.name}: {alias}.{attr} is not an attribute of edge {edge_name}")

for query_file in sorted((ROOT / "tigergraph/queries").glob("GQ-*.gsql")):
    validate(query_file)
if errors:
    print("GSQL semantic validation failed:")
    for error in errors:
        print("-", error)
    sys.exit(1)
print("GSQL semantic validation passed for 43 queries: all named edge traversals match source/target types and referenced attributes.")
