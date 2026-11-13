"""Bounded local scan journal; no user accounts or credentials stored."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


class ScanJournal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, mode TEXT NOT NULL, payload TEXT NOT NULL)")

    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def record(self, mode: str, payload: dict):
        if mode not in {"DEMO", "PUBLIC_READ_ONLY"}:
            raise ValueError("Unknown scan mode")
        with self._db() as db:
            db.execute("INSERT INTO scans(created_at,mode,payload) VALUES(?,?,?)", (
                datetime.now(timezone.utc).isoformat(), mode, json.dumps(payload, separators=(",", ":"))
            ))
            db.execute("DELETE FROM scans WHERE id NOT IN (SELECT id FROM scans ORDER BY id DESC LIMIT 60)")

    def recent(self, limit: int = 15) -> list[dict]:
        limit = max(1, min(int(limit), 60))
        with self._db() as db:
            return [{"id": row["id"], "created_at": row["created_at"], "mode": row["mode"],
                     "payload": json.loads(row["payload"])} for row in db.execute(
                "SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))]
