from __future__ import annotations

from app.models.ingestion import IngestionEntityConfig


class ValidationEngine:
    def validate_header(self, config: IngestionEntityConfig, headers: list[str]) -> list[str]:
        missing = [col for col in config.required_columns if col not in headers]
        return [f"Missing required column: {col}" for col in missing]

    def validate_record(self, config: IngestionEntityConfig, record: dict[str, str]) -> list[str]:
        errors = []
        for col in config.required_columns:
            value = record.get(col)
            if value is None or str(value).strip() == "":
                errors.append(f"Required column {col} is empty")
        return errors
