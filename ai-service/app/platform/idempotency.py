from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class IdempotencyStore(Protocol):
    def get(self, key: str) -> dict | None:
        ...

    def put(self, key: str, value: dict, ttl_seconds: int) -> None:
        ...


def idempotency_key(tenant: str, endpoint: str, payload: dict, contract_version: str) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    material = f"{tenant}|{endpoint}|{contract_version}|{hashlib.sha256(normalized.encode()).hexdigest()}"
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass
class InMemoryIdempotencyStore:
    values: dict[str, tuple[float, dict]]

    def __init__(self):
        self.values = {}

    def get(self, key: str) -> dict | None:
        row = self.values.get(key)
        if not row:
            return None
        expires_at, value = row
        if expires_at < time.time():
            self.values.pop(key, None)
            return None
        return value

    def put(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.values[key] = (time.time() + ttl_seconds, value)


class SQLiteIdempotencyStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("create table if not exists idempotency (key text primary key, expires_at real, value text)")

    def get(self, key: str) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("select expires_at, value from idempotency where key=?", (key,)).fetchone()
        if not row:
            return None
        expires_at, value = row
        if expires_at < time.time():
            return None
        return json.loads(value)

    def put(self, key: str, value: dict, ttl_seconds: int) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "insert or replace into idempotency(key, expires_at, value) values(?, ?, ?)",
                (key, time.time() + ttl_seconds, json.dumps(value, ensure_ascii=False, sort_keys=True)),
            )
