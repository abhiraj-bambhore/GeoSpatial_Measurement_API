"""Database abstraction layer supporting Supabase and local SQLite fallback.

Provides a unified repository interface for storing files and measurements.
If Supabase is unreachable or credentials are not configured, it gracefully falls back
to SQLite so the application is completely robust and production-resilient.
"""

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path("data/geospatial.db")


class DatabaseRepository:
    def __init__(self):
        self.use_supabase = False
        self.supabase_client = None
        self._init_sqlite()
        self._init_supabase()

    def _init_sqlite(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    feature_count INTEGER DEFAULT 0,
                    crs TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    error_message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS measurements (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    feature_index INTEGER NOT NULL,
                    geometry_type TEXT NOT NULL,
                    geometry_wkt TEXT,
                    properties TEXT DEFAULT '{}',
                    measurement_type TEXT,
                    measurement_value REAL,
                    measurement_unit TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_measurements_file_id ON measurements (file_id)"
            )
            conn.commit()

    def _init_supabase(self):
        if not settings.supabase_url or not settings.supabase_key:
            logger.info(
                "Supabase credentials not configured. Operating with local SQLite repository."
            )
            return

        clean_url = settings.supabase_url.rstrip("/").removesuffix("/rest/v1")

        try:
            from supabase import create_client

            client = create_client(clean_url, settings.supabase_key)
            # Probe Supabase with a lightweight query
            client.table("files").select("id").limit(1).execute()
            self.supabase_client = client
            self.use_supabase = True
            logger.info("Connected to Supabase successfully.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Supabase not accessible (%s). Operating with local SQLite repository.",
                exc,
            )
            self.use_supabase = False

    def create_file(self, filename: str, file_path: str) -> dict[str, Any]:
        file_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        record = {
            "id": file_id,
            "filename": filename,
            "file_path": file_path,
            "feature_count": 0,
            "crs": None,
            "status": "PENDING",
            "error_message": None,
            "created_at": created_at,
        }

        # Write to SQLite
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO files (id, filename, file_path, feature_count, crs, status, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["filename"],
                    record["file_path"],
                    record["feature_count"],
                    record["crs"],
                    record["status"],
                    record["error_message"],
                    record["created_at"],
                ),
            )
            conn.commit()

        # If Supabase is active, mirror write
        if self.use_supabase and self.supabase_client:
            try:
                self.supabase_client.table("files").insert(record).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to mirror insert file to Supabase: %s", exc)

        return record

    def update_file(
        self,
        file_id: str,
        *,
        status: str | None = None,
        feature_count: int | None = None,
        crs: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
        if feature_count is not None:
            updates["feature_count"] = feature_count
        if crs is not None:
            updates["crs"] = crs
        if error_message is not None:
            updates["error_message"] = error_message

        if not updates:
            return self.get_file(file_id)

        set_clauses = [f"{k} = ?" for k in updates]
        values = list(updates.values()) + [file_id]

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                f"UPDATE files SET {', '.join(set_clauses)} WHERE id = ?",
                values,
            )
            conn.commit()

        if self.use_supabase and self.supabase_client:
            try:
                self.supabase_client.table("files").update(updates).eq("id", file_id).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to mirror update file to Supabase: %s", exc)

        return self.get_file(file_id)

    def get_file(self, file_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def list_files(self) -> list[dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def save_measurements(self, file_id: str, measurements: list[dict[str, Any]]) -> None:
        if not measurements:
            return

        now_iso = datetime.now(UTC).isoformat()
        records_to_insert = []
        for m in measurements:
            rec_id = str(uuid.uuid4())
            props = json.dumps(m.get("properties", {}))
            records_to_insert.append(
                (
                    rec_id,
                    file_id,
                    m.get("feature_index", 0),
                    m.get("geometry_type", "Unknown"),
                    m.get("geometry_wkt"),
                    props,
                    m.get("measurement_type"),
                    m.get("measurement_value"),
                    m.get("measurement_unit"),
                    now_iso,
                )
            )

        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(
                """
                INSERT INTO measurements (
                    id, file_id, feature_index, geometry_type, geometry_wkt,
                    properties, measurement_type, measurement_value, measurement_unit, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records_to_insert,
            )
            conn.commit()

        if self.use_supabase and self.supabase_client:
            try:
                supabase_records = [
                    {
                        "id": r[0],
                        "file_id": r[1],
                        "feature_index": r[2],
                        "geometry_type": r[3],
                        "geometry_wkt": r[4],
                        "properties": json.loads(r[5]),
                        "measurement_type": r[6],
                        "measurement_value": r[7],
                        "measurement_unit": r[8],
                        "created_at": r[9],
                    }
                    for r in records_to_insert
                ]
                self.supabase_client.table("measurements").insert(supabase_records).execute()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to mirror measurements to Supabase: %s", exc)

    def get_measurements(self, file_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM measurements WHERE file_id = ? ORDER BY feature_index ASC",
                (file_id,),
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                if isinstance(d.get("properties"), str):
                    try:
                        d["properties"] = json.loads(d["properties"])
                    except Exception:  # noqa: BLE001
                        d["properties"] = {}
                results.append(d)
            return results


repo = DatabaseRepository()
