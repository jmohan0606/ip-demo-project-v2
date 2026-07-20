from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_python_import(module: str) -> dict:
    try:
        importlib.import_module(module)
        return {"name": module, "status": "passed"}
    except Exception as exc:
        return {"name": module, "status": "failed", "error": str(exc)}


def check_path(path: str) -> dict:
    p = ROOT / path
    return {"path": path, "exists": p.exists(), "type": "dir" if p.is_dir() else "file" if p.is_file() else "missing"}


def check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> None:
    checks = {
        "python_version": sys.version,
        "cwd": str(ROOT),
        "imports": [
            check_python_import("fastapi"),
            check_python_import("pydantic"),
            check_python_import("requests"),
        ],
        "paths": [
            check_path("app"),
            check_path("frontend"),
            check_path("data"),
            check_path("docs"),
            check_path(".env.example"),
        ],
        "ports": {
            "api_8000_in_use": check_port("127.0.0.1", 8000),
            "frontend_3000_in_use": check_port("127.0.0.1", 3000),
        },
    }
    out = ROOT / "docs/runtime_preflight_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
