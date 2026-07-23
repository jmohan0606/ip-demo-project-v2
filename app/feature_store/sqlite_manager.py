from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.config.settings import get_settings, resolve_app_path


class SQLiteManager:
    """Thin SQLite access used by the ingestion checkpoint repository and the
    tier-2 local store. One file DB (SQLITE_DB_PATH), dict rows."""

    def __init__(self, db_path: str | None = None) -> None:
        # A7: anchored at the repo root so the live DB never depends on launch dir
        self.db_path = str(resolve_app_path(db_path or get_settings().sqlite_db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)
            conn.commit()

    def initialize_foundation_tables(self) -> None:
        """No-op hook kept for CheckpointRepository compatibility — V2 creates its
        tables explicitly where they are owned."""
        return None
