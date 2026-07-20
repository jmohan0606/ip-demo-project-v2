#!/usr/bin/env python3
"""Client-environment npm dependency pre-check (run FIRST on the client machine).

Parses frontend/package.json (dependencies + devDependencies) and checks each
package against the client npm registry (JPMC Artifactory by default) BEFORE
`npm install` is attempted.

For each package:
  AVAILABLE        — a published version satisfying the declared range exists
  VERSION-MISMATCH — the package exists but no version satisfies the range
                     (or the range syntax isn't evaluated — stated explicitly)
  MISSING          — the package is not on the registry

Exit codes: 0 = all deps available; 1 = any MISSING/VERSION-MISMATCH;
2 = registry unreachable (clear message, no traceback).

Usage:
  python scripts/check_client_npm.py                      # client artifactory
  python scripts/check_client_npm.py --registry https://registry.npmjs.org
  CLIENT_NPM_REGISTRY=<url> python scripts/check_client_npm.py

Auth note: if the registry returns 401/403, configure frontend/.npmrc from the
committed template frontend/.npmrc.client-template (see CLIENT_ENV_SETUP.md §6).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_REGISTRY = "https://artifacts-read.gkp.jpmchase.net/artifactory/api/npm/npm/"
REPO_ROOT = Path(__file__).resolve().parent.parent

STATUS_AVAILABLE = "AVAILABLE"
STATUS_MISMATCH = "VERSION-MISMATCH"
STATUS_MISSING = "MISSING"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def parse_semver(v: str) -> tuple[int, int, int] | None:
    m = _SEMVER_RE.match(v.strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def satisfies(version: str, range_spec: str) -> bool | None:
    """Minimal semver-range check for the forms this repo actually uses
    (^x.y.z, ~x.y.z, exact, >=x.y.z, *, latest). Returns None when the range
    syntax isn't one of those (caller reports it as not-evaluated)."""
    v = parse_semver(version)
    if v is None:
        return None
    if "-" in version:  # npm semantics: prereleases never satisfy a plain range
        return False
    spec = range_spec.strip()
    if spec in ("*", "latest", ""):
        return True
    if spec.startswith("^"):
        b = parse_semver(spec[1:])
        if b is None:
            return None
        if b[0] > 0:
            return v[0] == b[0] and v >= b
        return v[0] == 0 and v[1] == b[1] and v >= b
    if spec.startswith("~"):
        b = parse_semver(spec[1:])
        return None if b is None else (v[0] == b[0] and v[1] == b[1] and v >= b)
    if spec.startswith(">="):
        b = parse_semver(spec[2:])
        return None if b is None else v >= b
    b = parse_semver(spec)  # exact pin
    return None if b is None else v == b


def fetch_packument(registry: str, name: str, timeout: float) -> dict | None:
    quoted = urllib.parse.quote(name, safe="@")  # scoped packages: @scope%2Fname
    quoted = quoted.replace("/", "%2F")
    url = f"{registry.rstrip('/')}/{quoted}"
    req = urllib.request.Request(
        url,
        headers={
            # abbreviated packument — much smaller, still lists all versions
            "Accept": "application/vnd.npm.install-v1+json, application/json;q=0.8",
            "User-Agent": "iperform-client-dep-check/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def check_package(registry: str, name: str, range_spec: str, timeout: float) -> tuple[str, str]:
    doc = fetch_packument(registry, name, timeout)
    if doc is None:
        return STATUS_MISSING, "not on registry"
    versions = list((doc.get("versions") or {}).keys())
    if not versions:
        return STATUS_MISSING, "no published versions"
    evaluated = [(v, satisfies(v, range_spec)) for v in versions]
    matches = [v for v, s in evaluated if s]
    if matches:
        best = max((parse_semver(v), v) for v in matches if parse_semver(v))[1]
        return STATUS_AVAILABLE, f"best match {best}"
    if all(s is None for _, s in evaluated):
        latest = (doc.get("dist-tags") or {}).get("latest", versions[-1])
        return STATUS_AVAILABLE, f"exists (range '{range_spec}' not evaluated); latest {latest}"
    latest = (doc.get("dist-tags") or {}).get("latest", versions[-1])
    return STATUS_MISMATCH, f"range '{range_spec}' unsatisfied; latest on registry {latest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--registry",
        default=os.environ.get("CLIENT_NPM_REGISTRY", DEFAULT_REGISTRY),
        help=f"npm registry URL (default: $CLIENT_NPM_REGISTRY or {DEFAULT_REGISTRY})",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    pkg = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    deps: list[tuple[str, str, str]] = [
        *(("dependencies", n, r) for n, r in (pkg.get("dependencies") or {}).items()),
        *(("devDependencies", n, r) for n, r in (pkg.get("devDependencies") or {}).items()),
    ]
    print(f"Checking {len(deps)} npm packages against {args.registry}\n")

    # Reachability probe first — fail gracefully.
    try:
        fetch_packument(args.registry, "react", args.timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            print(f"ERROR: registry requires authentication (HTTP {exc.code}).")
            print("  Configure frontend/.npmrc from frontend/.npmrc.client-template")
            print("  (uncomment always-auth/_authToken and supply a token — CLIENT_ENV_SETUP.md §6).")
            return 2
        print(f"ERROR: registry probe failed: HTTP {exc.code} {exc.reason}")
        return 2
    except Exception as exc:
        print("ERROR: the npm registry is not reachable from this machine.")
        print(f"  Registry: {args.registry}")
        print(f"  Cause: {exc.__class__.__name__}: {exc}")
        print("  If you are NOT on the client network, pass --registry https://registry.npmjs.org")
        print("  to validate the check logic, and re-run this on the client machine.")
        return 2

    rows = []
    failures = 0
    for group, name, range_spec in deps:
        try:
            status, detail = check_package(args.registry, name, range_spec, args.timeout)
        except Exception as exc:
            status, detail = STATUS_MISSING, f"lookup failed: {exc.__class__.__name__}: {exc}"
        if status != STATUS_AVAILABLE:
            failures += 1
        rows.append((group, f"{name}@{range_spec}", status, detail))

    name_w = max(len(r[1]) for r in rows) + 2
    grp_w = max(len(r[0]) for r in rows) + 2
    print(f"{'GROUP':<{grp_w}}{'PACKAGE':<{name_w}}{'STATUS':<18}DETAIL")
    print("-" * (grp_w + name_w + 18 + 40))
    for group, label, status, detail in sorted(rows, key=lambda r: (r[2] == STATUS_AVAILABLE, r[0], r[1].lower())):
        print(f"{group:<{grp_w}}{label:<{name_w}}{status:<18}{detail}")

    n_avail = sum(1 for r in rows if r[2] == STATUS_AVAILABLE)
    print(f"\nSummary: {n_avail}/{len(rows)} AVAILABLE, "
          f"{sum(1 for r in rows if r[2] == STATUS_MISMATCH)} VERSION-MISMATCH, "
          f"{sum(1 for r in rows if r[2] == STATUS_MISSING)} MISSING")
    if failures:
        print(f"FAIL: {failures} package issue(s) — resolve before `npm install` on the client machine.")
        return 1
    print("PASS: every frontend dependency is available from this registry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
