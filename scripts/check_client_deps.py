#!/usr/bin/env python3
"""Client-environment PyPI dependency pre-check (run FIRST on the client machine).

Parses pyproject.toml — core dependencies plus EVERY optional group (dev, aws, ml,
gds, …) plus the client-only `smart_sdk` — and checks each package against the
client PyPI index (JPMC Artifactory by default) BEFORE any install is attempted,
so missing libraries are found upfront, not mid-build.

For each requirement:
  AVAILABLE        — a Python 3.12-compatible release satisfying the pin exists
  VERSION-MISMATCH — the package exists but no release satisfies the pin (or none
                     is 3.12-compatible); the best available version is shown
  MISSING          — the package is not on the index at all

Exit codes: 0 = all required deps available; 1 = a required dep MISSING or
VERSION-MISMATCH; 2 = index unreachable (clear message, no traceback).

Usage:
  python scripts/check_client_deps.py                      # client artifactory
  python scripts/check_client_deps.py --index-url https://pypi.org/simple
  CLIENT_PYPI_INDEX=<url> python scripts/check_client_deps.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name
    from packaging.version import Version
except ImportError:  # pragma: no cover
    sys.exit(
        "The 'packaging' library is required (ships with pip/setuptools): pip install packaging"
    )

DEFAULT_INDEX = "https://artifacts-read.gkp.jpmchase.net/artifactory/api/pypi/pypi/simple"
PYTHON_TARGET = Version("3.12")
REPO_ROOT = Path(__file__).resolve().parent.parent

# At-risk packages and their documented fallbacks (CLIENT_ENV_SETUP.md §2,
# "Library fallback table") — printed whenever one is not cleanly AVAILABLE.
AT_RISK_FALLBACKS: dict[str, str] = {
    "torch": (
        "Large native wheel. Install torch first from the artifactory torch channel, then a "
        "matching torch-geometric. App runs WITHOUT it — app/ml/* guard the imports and fall "
        "back to deterministic scorers."
    ),
    "torch-geometric": (
        "Install AFTER torch (matching version). App runs without it — GNN falls back to "
        "deterministic feature projection."
    ),
    "sentence-transformers": (
        "Not needed at all when EMBEDDING_CLIENT_MODE=azure (SmartSDK embeddings); otherwise "
        "pre-stage the model files."
    ),
    "chromadb": (
        "Needs onnxruntime for its default embedder (unused — we pass our own vectors). Pin "
        "onnxruntime if the default build is unavailable."
    ),
    "pytigergraph": (
        "Base pyTigerGraph (this core dep) is all the app uses today — graph algorithms run in "
        "networkx and GraphSAGE in local PyTorch Geometric. The pyTigerGraph[gds] extra is NOT "
        "installed by default (its optional group is commented out in pyproject.toml); it is "
        "needed only for the future native TigerGraph GDS/GNN conversion — see GRAPH_ML_AND_GDS.md."
    ),
    "smart-sdk": (
        "Client-artifactory ONLY (never on public PyPI). Guarded import — absence never blocks "
        "boot in mock/claude/real mode. Required only for the azure (SmartSDK/Fusion) modes."
    ),
    "cdaosdk-all": (
        "Client-artifactory ONLY (cdao SDK; [tool.uv.sources] pins it to the 'artifacts' index). "
        "The [openai] extra serves BOTH the PRIMARY client LLM path (LLM_CLIENT_MODE=cdao_openai) "
        "and the PRIMARY client embedding path (EMBEDDING_CLIENT_MODE=cdao_openai) — same SDK, one "
        "install, one PCL login. Guarded imports; if unavailable, fall back to the azure (SmartSDK) "
        "modes for both."
    ),
    "cdaosmart-sdk": (
        "Client-artifactory ONLY (pinned ==2.2.0 per the client reference project; "
        "[tool.uv.sources] → 'artifacts'). Not imported by this app's core paths — mirrors the "
        "client agent stack; absence never blocks boot."
    ),
    "cdaosmart-evals": (
        "Client-artifactory ONLY (pinned ==0.2.3 per the client reference project; "
        "[tool.uv.sources] → 'artifacts'). Eval tooling only; absence never blocks boot."
    ),
}

STATUS_AVAILABLE = "AVAILABLE"
STATUS_MISMATCH = "VERSION-MISMATCH"
STATUS_MISSING = "MISSING"


def load_requirements(pyproject_path: Path) -> list[tuple[str, str, Requirement]]:
    """(group, raw_spec, Requirement) for core deps + every optional group + smart_sdk."""
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    out: list[tuple[str, str, Requirement]] = []
    for raw in project.get("dependencies", []):
        out.append(("core", raw, Requirement(raw)))
    for group, deps in project.get("optional-dependencies", {}).items():
        for raw in deps:
            out.append((group, raw, Requirement(raw)))
    # Client-only, intentionally not declared in pyproject (see its comment):
    out.append(("client-only", "smart_sdk", Requirement("smart_sdk")))
    return out


def fetch_project(index_url: str, name: str, timeout: float) -> dict | None:
    """PEP 691 JSON simple-index page for a project; None if 404. Falls back to
    PEP 503 HTML parsing when the index doesn't serve JSON."""
    url = f"{index_url.rstrip('/')}/{canonicalize_name(name)}/"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.pypi.simple.v1+json, text/html;q=0.1",
            "User-Agent": "iperform-client-dep-check/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if "json" in ctype:
        return json.loads(body)
    # PEP 503 HTML: synthesize a minimal PEP 691 shape from anchor tags.
    html = body.decode("utf-8", errors="replace")
    files = []
    for m in re.finditer(r"<a[^>]*>([^<]+)</a>", html):
        tag = m.group(0)
        rp = re.search(r'data-requires-python="([^"]*)"', tag)
        files.append({
            "filename": m.group(1).strip(),
            "requires-python": rp.group(1) if rp else None,
        })
    return {"files": files}


def file_version(filename: str) -> Version | None:
    """Release version from a wheel/sdist filename, using packaging's canonical
    parsers (handles build tags like torch-2.10.0-3-cp314-...)."""
    from packaging.utils import parse_sdist_filename, parse_wheel_filename

    try:
        if filename.endswith(".whl"):
            return parse_wheel_filename(filename)[1]
        if filename.endswith((".tar.gz", ".zip")):
            return parse_sdist_filename(filename)[1]
    except Exception:
        return None
    return None


def py312_ok(requires_python: str | None) -> bool:
    if not requires_python:
        return True
    try:
        return PYTHON_TARGET in SpecifierSet(requires_python.replace("&quot;", '"'))
    except Exception:
        return True  # unparseable metadata: don't reject on it


def check_requirement(index_url: str, req: Requirement, timeout: float) -> tuple[str, str]:
    """-> (status, detail)."""
    page = fetch_project(index_url, req.name, timeout)
    if page is None:
        return STATUS_MISSING, "not on index"

    compat: set[Version] = set()
    incompat: set[Version] = set()
    for f in page.get("files", []):
        ver = file_version(f.get("filename", ""))
        if ver is None:
            continue
        (compat if py312_ok(f.get("requires-python")) else incompat).add(ver)

    all_versions = compat | incompat
    if not all_versions:
        return STATUS_MISSING, "no parseable releases on index"

    matching = sorted(v for v in compat if not v.is_prerelease and v in req.specifier)
    if matching:
        return STATUS_AVAILABLE, f"best match {matching[-1]}"
    latest = max(all_versions)
    spec = str(req.specifier) or "(any)"
    reason = "no 3.12-compatible release" if any(v in req.specifier for v in incompat) else f"pin {spec} unsatisfied"
    return STATUS_MISMATCH, f"{reason}; latest on index {latest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--index-url",
        default=os.environ.get("CLIENT_PYPI_INDEX", DEFAULT_INDEX),
        help=f"PEP 503/691 simple index URL (default: $CLIENT_PYPI_INDEX or {DEFAULT_INDEX})",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    requirements = load_requirements(REPO_ROOT / "pyproject.toml")
    print(f"Checking {len(requirements)} requirements against {args.index_url}")
    print(f"Python target: {PYTHON_TARGET}\n")

    # Reachability probe first — fail gracefully, not per-row.
    try:
        fetch_project(args.index_url, "pip", args.timeout)
    except Exception as exc:
        print("ERROR: the package index is not reachable from this machine.")
        print(f"  Index: {args.index_url}")
        print(f"  Cause: {exc.__class__.__name__}: {exc}")
        print("  If you are NOT on the client network, pass --index-url https://pypi.org/simple")
        print("  to validate the check logic, and re-run this on the client machine.")
        return 2

    rows: list[tuple[str, str, str, str, str]] = []
    failures = 0
    at_risk_notes: list[tuple[str, str]] = []
    for group, raw, req in requirements:
        try:
            status, detail = check_requirement(args.index_url, req, args.timeout)
        except Exception as exc:
            status, detail = STATUS_MISSING, f"lookup failed: {exc.__class__.__name__}: {exc}"
        key = canonicalize_name(req.name)
        risky = key in AT_RISK_FALLBACKS
        if status != STATUS_AVAILABLE:
            # Only the core group is REQUIRED; optional groups (ml/gds/aws/dev) and the
            # client-only smart_sdk all have documented fallbacks and warn instead.
            if group == "core":
                failures += 1
            if risky:
                at_risk_notes.append((raw, AT_RISK_FALLBACKS[key]))
        rows.append((group, raw, status, detail, "AT-RISK" if risky else ""))

    name_w = max(len(r[1]) for r in rows) + 2
    grp_w = max(len(r[0]) for r in rows) + 2
    print(f"{'GROUP':<{grp_w}}{'REQUIREMENT':<{name_w}}{'STATUS':<18}{'RISK':<9}DETAIL")
    print("-" * (grp_w + name_w + 27 + 40))
    for group, raw, status, detail, risk in sorted(rows, key=lambda r: (r[2] == STATUS_AVAILABLE, r[0], r[1].lower())):
        print(f"{group:<{grp_w}}{raw:<{name_w}}{status:<18}{risk:<9}{detail}")

    if at_risk_notes:
        print("\nAt-risk packages not cleanly available — documented fallbacks (CLIENT_ENV_SETUP.md §2):")
        for raw, fallback in at_risk_notes:
            print(f"  * {raw}\n      -> {fallback}")

    n_avail = sum(1 for r in rows if r[2] == STATUS_AVAILABLE)
    print(f"\nSummary: {n_avail}/{len(rows)} AVAILABLE, "
          f"{sum(1 for r in rows if r[2] == STATUS_MISMATCH)} VERSION-MISMATCH, "
          f"{sum(1 for r in rows if r[2] == STATUS_MISSING)} MISSING")
    if failures:
        print(f"FAIL: {failures} required dependency issue(s) — resolve before installing on the client machine.")
        return 1
    print("PASS: every required dependency is available from this index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
