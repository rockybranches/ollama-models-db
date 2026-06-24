from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .models import ModelEntry, ModelTag

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    url TEXT,
    pull_count INTEGER,
    tag_count INTEGER,
    updated_text TEXT,
    updated_timestamp TEXT,
    capabilities TEXT,
    sizes TEXT,
    is_cloud INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL REFERENCES models(name),
    tag TEXT NOT NULL,
    size_gb REAL,
    context_window INTEGER,
    modalities TEXT,
    is_latest INTEGER DEFAULT 0,
    is_mlx INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT (datetime('now')),
    last_updated TEXT DEFAULT (datetime('now')),
    UNIQUE(model_name, tag)
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL REFERENCES models(name),
    pull_count INTEGER,
    tag_count INTEGER,
    snapshot_date TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE(model_name, snapshot_date)
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def model_exists(self, name: str) -> bool:
        cur = self.connect().execute("SELECT 1 FROM models WHERE name = ?", (name,))
        return cur.fetchone() is not None

    def upsert_model(self, entry: ModelEntry) -> None:
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO models (name, description, url, pull_count, tag_count,
                                updated_text, updated_timestamp, capabilities,
                                sizes, is_cloud, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                url = excluded.url,
                pull_count = excluded.pull_count,
                tag_count = excluded.tag_count,
                updated_text = excluded.updated_text,
                updated_timestamp = excluded.updated_timestamp,
                capabilities = excluded.capabilities,
                sizes = excluded.sizes,
                is_cloud = excluded.is_cloud,
                last_updated = datetime('now')
            """,
            (
                entry.name,
                entry.description,
                entry.url,
                entry.pull_count,
                entry.tag_count,
                entry.updated_text,
                entry.updated_timestamp.isoformat() if entry.updated_timestamp else None,
                json.dumps(entry.capabilities),
                json.dumps(entry.sizes),
                1 if entry.is_cloud else 0,
            ),
        )
        conn.commit()

    def upsert_tag(self, tag: ModelTag) -> None:
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO model_tags (model_name, tag, size_gb, context_window,
                                    modalities, is_latest, is_mlx, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(model_name, tag) DO UPDATE SET
                size_gb = excluded.size_gb,
                context_window = excluded.context_window,
                modalities = excluded.modalities,
                is_latest = excluded.is_latest,
                is_mlx = excluded.is_mlx,
                last_updated = datetime('now')
            """,
            (
                tag.model_name,
                tag.tag,
                tag.size_gb,
                tag.context_window,
                json.dumps(tag.modalities),
                1 if tag.is_latest else 0,
                1 if tag.is_mlx else 0,
            ),
        )
        conn.commit()

    def record_history(self, entry: ModelEntry) -> None:
        today = date.today().isoformat()
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO history (model_name, pull_count, tag_count, snapshot_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(model_name, snapshot_date) DO UPDATE SET
                pull_count = excluded.pull_count,
                tag_count = excluded.tag_count
            """,
            (entry.name, entry.pull_count, entry.tag_count, today),
        )
        conn.commit()

    def get_model(self, name: str) -> Optional[dict]:
        cur = self.connect().execute("SELECT * FROM models WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_tags(self, model_name: str) -> list[dict]:
        cur = self.connect().execute(
            "SELECT * FROM model_tags WHERE model_name = ? ORDER BY tag", (model_name,)
        )
        return [dict(r) for r in cur.fetchall()]

    def list_models(
        self,
        capability: Optional[str] = None,
        cloud: Optional[bool] = None,
        sort: str = "name",
        query: Optional[str] = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list = []

        if capability:
            clauses.append("capabilities LIKE ?")
            params.append(f'%"{capability}"%')

        if cloud is not None:
            clauses.append("is_cloud = ?")
            params.append(1 if cloud else 0)

        if query:
            clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        where = ""
        if clauses:
            where = " WHERE " + " AND ".join(clauses)

        allowed_sorts = {"name", "pull_count", "tag_count", "last_updated", "first_seen"}
        if sort not in allowed_sorts:
            sort = "name"

        cur = self.connect().execute(
            f"SELECT * FROM models{where} ORDER BY {sort}", params
        )
        return [dict(r) for r in cur.fetchall()]

    def get_stats(self) -> dict:
        conn = self.connect()
        stats = {}
        stats["total_models"] = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        stats["total_tags"] = conn.execute("SELECT COUNT(*) FROM model_tags").fetchone()[0]
        stats["total_history"] = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        stats["cloud_models"] = conn.execute(
            "SELECT COUNT(*) FROM models WHERE is_cloud = 1"
        ).fetchone()[0]

        row = conn.execute(
            "SELECT MAX(last_updated) FROM models"
        ).fetchone()[0]
        stats["last_updated"] = row

        top = conn.execute(
            "SELECT name, pull_count FROM models ORDER BY pull_count DESC LIMIT 10"
        ).fetchall()
        stats["top_pulls"] = [dict(r) for r in top]

        cap_count = conn.execute(
            "SELECT capabilities FROM models WHERE capabilities IS NOT NULL"
        ).fetchall()
        caps: dict[str, int] = {}
        for r in cap_count:
            for c in json.loads(r[0]):
                caps[c] = caps.get(c, 0) + 1
        stats["capability_counts"] = caps

        return stats
