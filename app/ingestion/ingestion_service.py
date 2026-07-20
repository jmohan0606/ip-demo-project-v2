from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from app.config.settings import get_settings
from app.ingestion.checkpoint_repository import CheckpointRepository
from app.ingestion.delta_detector import DeltaDetector
from app.ingestion.entity_registry import get_entity_config, list_entity_configs
from app.ingestion.tigergraph_upsert import TigerGraphUpsertClient
from app.ingestion.validation_engine import ValidationEngine
from app.models.ingestion import (
    DeltaAction,
    IngestionBatchStatus,
    IngestionRecordResult,
    IngestionRunRequest,
    IngestionRunResponse,
    IngestionStatus,
)
from app.shared.ids import timestamp_id

# Persist the batch checkpoint every N rows (plus at every batch boundary and on
# completion/failure) — one SQLite fsync per N rows instead of per row.
_CHECKPOINT_EVERY = 200


class IngestionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.checkpoints = CheckpointRepository()
        self.validator = ValidationEngine()
        self.delta = DeltaDetector(self.checkpoints)
        self.upsert = TigerGraphUpsertClient()
        # Source-of-truth foundation sample data root (manifest file paths are
        # relative to it: vertices/*.csv and edges/*.csv). See TIGERGRAPH_AUDIT.md.
        self.sample_data_dir = Path(self.settings.foundation_dir) / "data" / "sample"

    def list_entities(self) -> list[dict]:
        return [config.model_dump() for config in list_entity_configs()]

    def list_batches(self) -> list[dict]:
        return self.checkpoints.list_batches()

    def _count_records(self, file_path: Path) -> int:
        with file_path.open(encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)

    def run_entity_ingestion(self, request: IngestionRunRequest) -> IngestionRunResponse:
        config = get_entity_config(request.entity_name)
        file_name = request.file_name or config.csv_file_name
        file_path = self.sample_data_dir / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        is_edge = config.kind == "edge"
        from_col = config.from_column or "from_id"
        to_col = config.to_column or "to_id"

        total_records = self._count_records(file_path)
        previous = self.checkpoints.latest_batch(config.entity_name, file_name) if request.resume else None

        should_resume = (
            request.resume
            and previous is not None
            and previous.status in {IngestionStatus.FAILED, IngestionStatus.PAUSED, IngestionStatus.RUNNING}
        )
        start_row = previous.last_processed_row + 1 if should_resume else 1

        status = IngestionBatchStatus(
            batch_id=previous.batch_id if should_resume else timestamp_id("batch"),
            entity_name=config.entity_name,
            file_name=file_name,
            status=IngestionStatus.RUNNING,
            total_records=total_records,
            processed_records=previous.processed_records if should_resume else 0,
            created_records=previous.created_records if should_resume else 0,
            updated_records=previous.updated_records if should_resume else 0,
            skipped_records=previous.skipped_records if should_resume else 0,
            failed_records=previous.failed_records if should_resume else 0,
            last_processed_row=previous.last_processed_row if should_resume else 0,
            progress_percent=previous.progress_percent if should_resume else 0,
            message="Running",
        )
        self.checkpoints.save_batch(status)

        results: list[IngestionRecordResult] = []
        batch_size = request.batch_size or config.batch_size

        # One read for all known hashes; one bulk write per flush — instead of a
        # SQLite connection + fsync per row (untenable at 122K edge rows).
        known_hashes = self.checkpoints.get_hashes(config.entity_name)
        pending_rows: list[dict] = []
        pending_hashes: list[tuple[str, str]] = []
        pending_first_row: list[int] = []  # row number of the first unflushed row

        def _record_pk(record: dict) -> str:
            if is_edge:
                return f"{record.get(from_col, '')}->{record.get(to_col, '')}"
            return record.get(config.primary_key, "")

        def _flush_writes() -> None:
            """Push the accumulated rows to the graph in ONE adapter call, then
            persist their hashes in one transaction."""
            if not pending_rows:
                return
            if not request.dry_run:
                if is_edge:
                    self.upsert.upsert_edge_rows(config.tigergraph_vertex, list(pending_rows))
                else:
                    self.upsert.upsert_vertex_rows(
                        config.tigergraph_vertex, list(pending_rows), id_column=config.primary_key
                    )
                self.checkpoints.upsert_hashes(config.entity_name, pending_hashes)
            pending_rows.clear()
            pending_hashes.clear()
            pending_first_row.clear()

        def _save_status() -> None:
            status.updated_at = datetime.utcnow()
            self.checkpoints.save_batch(status)

        with file_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header_errors = self.validator.validate_header(config, reader.fieldnames or [])
            if header_errors:
                status.status = IngestionStatus.FAILED
                status.message = "; ".join(header_errors)
                _save_status()
                return IngestionRunResponse(batch_status=status, records=[])

            for row_number, record in enumerate(reader, start=1):
                if row_number < start_row:
                    continue

                primary_key = _record_pk(record)
                try:
                    validation_errors = self.validator.validate_record(config, record)
                    if validation_errors:
                        raise ValueError("; ".join(validation_errors))

                    new_hash = self.delta.row_hash(record)
                    old_hash = known_hashes.get(primary_key)
                    if old_hash == new_hash:
                        action = DeltaAction.SKIP
                        status.skipped_records += 1
                        message = "Unchanged"
                    else:
                        action = DeltaAction.CREATE if old_hash is None else DeltaAction.UPDATE
                        if not pending_rows:
                            pending_first_row.append(row_number)
                        pending_rows.append(record)
                        pending_hashes.append((primary_key, new_hash))
                        known_hashes[primary_key] = new_hash
                        if action == DeltaAction.CREATE:
                            status.created_records += 1
                        else:
                            status.updated_records += 1
                        message = action.value

                    status.processed_records += 1
                    status.last_processed_row = row_number
                    status.progress_percent = (
                        round((status.last_processed_row / total_records) * 100, 2) if total_records else 100
                    )
                    if status.processed_records % _CHECKPOINT_EVERY == 0:
                        _save_status()

                    results.append(
                        IngestionRecordResult(
                            row_number=row_number,
                            entity_name=config.entity_name,
                            primary_key=primary_key,
                            action=action,
                            success=True,
                            message=message,
                        )
                    )

                except Exception as exc:
                    status.failed_records += 1
                    status.processed_records += 1
                    status.last_processed_row = row_number
                    status.progress_percent = (
                        round((status.last_processed_row / total_records) * 100, 2) if total_records else 100
                    )
                    status.status = IngestionStatus.FAILED
                    status.message = f"Failed at row {row_number}: {exc}"
                    _save_status()
                    self.checkpoints.save_error(
                        error_id=timestamp_id("err"),
                        batch_id=status.batch_id,
                        entity_name=config.entity_name,
                        row_number=row_number,
                        primary_key=primary_key,
                        error_message=str(exc),
                        raw_record=record,
                    )
                    results.append(
                        IngestionRecordResult(
                            row_number=row_number,
                            entity_name=config.entity_name,
                            primary_key=primary_key,
                            action=DeltaAction.FAILED,
                            success=False,
                            message=str(exc),
                        )
                    )
                    return IngestionRunResponse(batch_status=status, records=results[-batch_size:])

                if len(results) >= batch_size:
                    # Return after one batch so UI can show progress and call repeatedly.
                    try:
                        _flush_writes()
                    except Exception as exc:  # graph write failed for this batch
                        status.status = IngestionStatus.FAILED
                        status.message = f"Graph write failed at row {row_number}: {exc}"
                        # rewind so resume re-reads the unflushed rows
                        if pending_first_row:
                            status.last_processed_row = pending_first_row[0] - 1
                        _save_status()
                        return IngestionRunResponse(batch_status=status, records=results[-batch_size:])
                    status.message = "Batch completed; call again to continue if needed."
                    _save_status()
                    return IngestionRunResponse(batch_status=status, records=results[-batch_size:])

        try:
            _flush_writes()
        except Exception as exc:
            status.status = IngestionStatus.FAILED
            status.message = f"Graph write failed on final flush: {exc}"
            if pending_first_row:
                status.last_processed_row = pending_first_row[0] - 1
            _save_status()
            return IngestionRunResponse(batch_status=status, records=results[-batch_size:])
        status.status = IngestionStatus.COMPLETED
        status.progress_percent = 100.0
        status.message = "Completed"
        _save_status()
        return IngestionRunResponse(batch_status=status, records=results[-batch_size:])
