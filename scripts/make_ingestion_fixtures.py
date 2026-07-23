"""Round 5 A9a — build data/fixtures/, the ingestion regression harness.

Fixtures are TEST INPUTS (not demo data): small CSVs in the exact column shape the
real builder produces (headers taken from the live ingestion manifest), plus the
four deliberate edge cases the round exists to catch:

  * a value containing a comma, a double-quote and a newline (quoting, A2)
  * a BOM-prefixed file                                       (encoding, A3)
  * a file with a deliberately wrong column name              (fail-loud, A1)
  * an empty optional value                                   (absent != empty, A1)

The base set is a copy of data/sample (same headers as the manifest — verified by
the pre-flight check on load); the special files overlay it. data/fixtures/ is
gitignored; regenerate any time with:  python scripts/make_ingestion_fixtures.py
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import APP_ROOT  # noqa: E402

FIXTURES = APP_ROOT / "data" / "fixtures"
SAMPLE = APP_ROOT / "data" / "sample"

ADVISOR_HEADER = ["advisor_sid", "advisor_name", "rep_code", "branch_cd", "standard_id", "data_source"]

# Special-case advisor rows (same header the manifest declares for phx_dm_v2_advisor):
#  FIX001 — quoted comma + quote + newline in the name (A2 round-trip)
#  FIX002 — empty OPTIONAL value (branch_cd) — legitimately skippable, never an error
#  FIX003 — plain row
ADVISOR_ROWS = [
    {"advisor_sid": "FIX001", "advisor_name": 'Alvarez, Katherine "Kat"\nSecond Line',
     "rep_code": "FX01", "branch_cd": "FXBR1", "standard_id": "SFIX001", "data_source": "REAL"},
    {"advisor_sid": "FIX002", "advisor_name": "Fixture Two",
     "rep_code": "FX02", "branch_cd": "", "standard_id": "SFIX002", "data_source": "REAL"},
    {"advisor_sid": "FIX003", "advisor_name": "Fixture Three",
     "rep_code": "FX03", "branch_cd": "FXBR3", "standard_id": "SFIX003", "data_source": "REAL"},
]


def _write(path: Path, header: list[str], rows: list[dict], bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    # base set: every manifest file, exact sample shape (headers == manifest columns)
    shutil.copytree(SAMPLE, FIXTURES)

    # overlay: special advisor file replaces the base one
    _write(FIXTURES / "vertices" / "advisor.csv", ADVISOR_HEADER, ADVISOR_ROWS)
    # BOM-prefixed variant (loaded via the file_name override in the harness)
    _write(FIXTURES / "vertices" / "advisor_bom.csv", ADVISOR_HEADER, ADVISOR_ROWS, bom=True)
    # deliberately wrong column name: advisor_name -> advisor_nm (must fail loudly)
    wrong_header = ["advisor_sid", "advisor_nm", "rep_code", "branch_cd", "standard_id", "data_source"]
    wrong_rows = [{**{k: v for k, v in r.items() if k != "advisor_name"},
                   "advisor_nm": r["advisor_name"]} for r in ADVISOR_ROWS]
    _write(FIXTURES / "vertices" / "advisor_wrong_column.csv", wrong_header, wrong_rows)

    files = sorted(p.relative_to(FIXTURES) for p in FIXTURES.rglob("*.csv"))
    print(f"wrote {len(files)} fixture CSVs under {FIXTURES}")
    for special in ["vertices/advisor.csv", "vertices/advisor_bom.csv", "vertices/advisor_wrong_column.csv"]:
        assert (FIXTURES / special).exists(), special
    print("special cases: quoted comma+quote+newline, empty optional, BOM, wrong column — present")


if __name__ == "__main__":
    main()
