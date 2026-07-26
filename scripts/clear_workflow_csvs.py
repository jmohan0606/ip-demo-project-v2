"""R16 migration — reset the commentary/anomaly dual-persistence CSVs to header-only.

Companion to docs/tigergraph_foundation/tigergraph/schema/
91_clear_commentary_anomalies.gsql (which clears the GRAPH): this script
clears the CSV side. The workflow persists commentary/anomaly records BOTH to
the graph and to the active data set's CSVs, so after the graph clear these
files would re-load the stale (pre-R16, collided-key) rows on the next
manifest run. Each file is truncated to its HEADER LINE ONLY — the file stays,
the column contract stays, only the data rows go.

Pure stdlib on purpose: runs with any Python >= 3.10, no project dependency
sync needed (uv can run it with --no-project).

Usage (dry-run by default — prints what WOULD be cleared, changes nothing):

    uv run --no-project python scripts/clear_workflow_csvs.py
    uv run --no-project python scripts/clear_workflow_csvs.py --yes        # actually clear
    uv run --no-project python scripts/clear_workflow_csvs.py --data-set sample --yes
    uv run --no-project python scripts/clear_workflow_csvs.py --dir /path/to/data/real --yes

Plain python works identically:  python scripts/clear_workflow_csvs.py --yes

Scope: ONLY the derived workflow files below — never source/revenue CSVs.
Evidence is included by default (the next generate-all rebuilds it in full,
exactly like the GSQL script); pass --keep-evidence to leave it.
Exit codes: 0 ok (incl. clean dry-run), 1 nothing found / a file failed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Kept in sync with app/v2/dataset/builder.csv_file_for and the entity list in
# docs/ROUND16_ACCEPTANCE.md §5 / 91_clear_commentary_anomalies.gsql.
WORKFLOW_FILES = [
    "vertices/phx_dm_v2_commentary_version.csv",
    "vertices/phx_dm_v2_commentary.csv",
    "vertices/phx_dm_v2_commentary_evaluation.csv",
    "vertices/phx_dm_v2_anomaly_scan.csv",
    "vertices/phx_dm_v2_anomaly.csv",
    "edges/phx_dm_v2_commentary_in_version.csv",
    "edges/phx_dm_v2_commentary_for_advisor.csv",
    "edges/phx_dm_v2_commentary_from_month.csv",
    "edges/phx_dm_v2_commentary_to_month.csv",
    "edges/phx_dm_v2_commentary_cites_driver.csv",
    "edges/phx_dm_v2_evaluation_of_commentary.csv",
    "edges/phx_dm_v2_anomaly_in_scan.csv",
    "edges/phx_dm_v2_anomaly_for_advisor.csv",
    "edges/phx_dm_v2_anomaly_cites_driver.csv",
]
EVIDENCE_FILES = [
    "vertices/phx_dm_v2_evidence.csv",
    "edges/phx_dm_v2_evidence_for_driver.csv",
]


def data_row_count(path: Path) -> int:
    """Physical lines after the header. Quoted embedded newlines make this an
    UPPER bound on logical rows — fine for a what-will-be-cleared report."""
    with path.open("rb") as f:
        return max(0, sum(1 for line in f if line.strip()) - 1)


def truncate_to_header(path: Path) -> None:
    """Keep the first line byte-for-byte (BOM and all); drop everything after.
    Readers are BOM-tolerant (utf-8-sig) and writers append with LF, so
    preserving the existing header bytes keeps every consumer working."""
    with path.open("rb") as f:
        header = f.readline()
    if not header.endswith(b"\n"):
        header += b"\n"
    with path.open("wb") as f:
        f.write(header)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset commentary/anomaly workflow CSVs to header-only "
                    "(R16 migration §5b). Dry-run unless --yes is given.")
    parser.add_argument("--data-set", default=os.environ.get("DATA_SET", "real"),
                        help="data set name under data/ (default: $DATA_SET or 'real')")
    parser.add_argument("--dir", default="",
                        help="explicit data-set directory (overrides --data-set)")
    parser.add_argument("--keep-evidence", action="store_true",
                        help="do NOT clear evidence files (default clears them; "
                             "generate-all rebuilds evidence in full)")
    parser.add_argument("--yes", action="store_true",
                        help="actually truncate; without it this is a dry-run")
    args = parser.parse_args()

    base = Path(args.dir) if args.dir else ROOT / "data" / args.data_set
    if not base.is_dir():
        print(f"ERROR: data-set directory not found: {base}", file=sys.stderr)
        return 1

    targets = WORKFLOW_FILES + ([] if args.keep_evidence else EVIDENCE_FILES)
    mode = "CLEARING" if args.yes else "DRY-RUN (pass --yes to clear)"
    print(f"{mode} — workflow CSVs under {base}\n")

    cleared = missing = failed = total_rows = 0
    for rel in targets:
        path = base / rel
        if not path.is_file():
            print(f"  MISSING  {rel}  (skipped — nothing to clear)")
            missing += 1
            continue
        try:
            rows = data_row_count(path)
            if args.yes:
                truncate_to_header(path)
            total_rows += rows
            cleared += 1
            verb = "cleared" if args.yes else "would clear"
            print(f"  OK       {rel}  ({verb} {rows} data row{'s' if rows != 1 else ''})")
        except OSError as exc:
            print(f"  FAILED   {rel}  ({exc})", file=sys.stderr)
            failed += 1

    print(f"\n{cleared} file(s) {'cleared' if args.yes else 'to clear'}, "
          f"{total_rows} data row(s), {missing} missing, {failed} failed")
    if args.yes and cleared:
        print("\nNext steps (docs/ROUND16_ACCEPTANCE.md §5):")
        print("  1. graph side, if not done: gsql docs/tigergraph_foundation/"
              "tigergraph/schema/91_clear_commentary_anomalies.gsql")
        print("  2. clear ingestion checkpoints for these entities so the screen "
              "matches: POST /ingestion/clear-checkpoints")
        print("  3. regenerate: python -m app.v2.commentary.generation_workflow "
              "&& python -m app.v2.anomalies.detection")
    if failed:
        return 1
    if cleared == 0:
        print("Nothing found to clear — check --data-set / --dir.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
