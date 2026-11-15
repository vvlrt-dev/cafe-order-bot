"""Order storage in SQLite (standard library)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STATUSES = ("new", "accepted", "ready", "cancelled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    user_id     INTEGER NOT NULL,
    chat_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    pickup_at   TEXT    NOT NULL,
    items_json  TEXT    NOT NULL,
    total       REAL    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'new'
);
"""


@dataclass
class Order:
    id: int
    created_at: datetime
    user_id: int
    chat_id: int
    name: str
    phone: str
    pickup_at: datetime
    items: list[dict]
    total: float
    status: str


class OrderStore:
    def __init__(self, path: Path | str):
        self._db = sqlite3.connect(str(path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    def create(self, *, user_id: int, chat_id: int, name: str, phone: str, pickup_at: datetime,
               items: list[dict], total: float, created_at: datetime) -> Order:
        cur = self._db.execute(
            "INSERT INTO orders (created_at, user_id, chat_id, name, phone, pickup_at, items_json, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (created_at.isoformat(), user_id, chat_id, name, phone, pickup_at.isoformat(), json.dumps(items), total),
        )
        self._db.commit()
        return self.get(cur.lastrowid)

    def get(self, order_id: int) -> Order | None:
        row = self._db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return self._to_order(row) if row else None

    def set_status(self, order_id: int, status: str) -> Order | None:
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}")
        self._db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        self._db.commit()
        return self.get(order_id)

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _to_order(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            name=row["name"],
            phone=row["phone"],
            pickup_at=datetime.fromisoformat(row["pickup_at"]),
            items=json.loads(row["items_json"]),
            total=row["total"],
            status=row["status"],
        )
