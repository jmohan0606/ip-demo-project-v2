#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
pattern = re.compile(r"PRINT\s+query_id|contract-template|\bTODO\b|\bPLACEHOLDER\b|dummy query", re.I)
hits = []
ignored_parts = {"node_modules", "dist", "__pycache__", ".git", "runtime"}
for path in root.rglob("*"):
    if any(part in ignored_parts for part in path.parts):
        continue
    if path.is_file() and path.suffix.lower() in {".gsql", ".py", ".ts", ".tsx", ".md", ".json"}:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pattern.search(text) and path.name not in {"check_no_placeholders.py", "validate_package.py"}:
            hits.append(str(path.relative_to(root)))
if hits:
    print("Placeholder markers found:")
    print("\n".join(hits))
    sys.exit(1)
print("No placeholder markers found in executable/source documentation files.")
