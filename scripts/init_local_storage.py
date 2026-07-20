from __future__ import annotations
from app.config.settings import get_settings
from app.feature_store.sqlite_manager import SQLiteManager


def main() -> None:
    settings = get_settings()
    settings.ensure_local_directories()
    SQLiteManager().initialize_foundation_tables()
    print("Local storage initialized.")
    print(f"SQLite DB: {settings.sqlite_db_path}")
    print(f"Chroma path: {settings.chroma_path}")


if __name__ == "__main__":
    main()
