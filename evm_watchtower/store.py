from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("DATABASE_PATH", "./watchtower.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists users (
                  id integer primary key autoincrement,
                  wallet text not null unique,
                  created_at integer not null
                );
                create table if not exists nonces (
                  address text primary key,
                  nonce text not null,
                  message text not null,
                  expires_at integer not null
                );
                create table if not exists sessions (
                  token text primary key,
                  user_id integer not null,
                  expires_at integer not null
                );
                create table if not exists telegram_settings (
                  user_id integer primary key,
                  bot_token text not null,
                  chat_id text not null,
                  enabled integer not null default 1
                );
                create table if not exists monitors (
                  id integer primary key autoincrement,
                  user_id integer not null,
                  address text not null,
                  label text not null default '',
                  chains_json text not null,
                  active integer not null default 1,
                  created_at integer not null
                );
                create table if not exists chain_state (
                  chain_key text primary key,
                  last_block integer not null
                );
                create table if not exists events (
                  id integer primary key autoincrement,
                  user_id integer not null,
                  monitor_id integer not null,
                  chain_key text not null,
                  event_key text not null unique,
                  tx_hash text not null,
                  block_number integer not null,
                  watched_address text not null,
                  action text not null,
                  direction text not null,
                  summary text not null,
                  details_json text not null,
                  created_at integer not null,
                  notified_at integer
                );
                """
            )

    def set_nonce(self, address: str, nonce: str, message: str, ttl_seconds: int = 600) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into nonces(address, nonce, message, expires_at)
                values (?, ?, ?, ?)
                on conflict(address) do update set nonce=excluded.nonce,
                  message=excluded.message, expires_at=excluded.expires_at
                """,
                (address, nonce, message, int(time.time()) + ttl_seconds),
            )

    def get_nonce(self, address: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "select * from nonces where address=? and expires_at>?",
                (address, int(time.time())),
            ).fetchone()

    def upsert_user(self, wallet: str) -> int:
        now = int(time.time())
        with self.connect() as conn:
            conn.execute(
                "insert or ignore into users(wallet, created_at) values (?, ?)",
                (wallet, now),
            )
            row = conn.execute("select id from users where wallet=?", (wallet,)).fetchone()
            return int(row["id"])

    def create_session(self, user_id: int, token: str, ttl_seconds: int = 30 * 24 * 3600) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into sessions(token, user_id, expires_at) values (?, ?, ?)",
                (token, user_id, int(time.time()) + ttl_seconds),
            )

    def session_user(self, token: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                select users.* from sessions
                join users on users.id=sessions.user_id
                where sessions.token=? and sessions.expires_at>?
                """,
                (token, int(time.time())),
            ).fetchone()

    def set_telegram(self, user_id: int, bot_token: str, chat_id: str, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into telegram_settings(user_id, bot_token, chat_id, enabled)
                values (?, ?, ?, ?)
                on conflict(user_id) do update set bot_token=excluded.bot_token,
                  chat_id=excluded.chat_id, enabled=excluded.enabled
                """,
                (user_id, bot_token, chat_id, int(enabled)),
            )

    def telegram_for_user(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "select * from telegram_settings where user_id=? and enabled=1",
                (user_id,),
            ).fetchone()

    def create_monitor(self, user_id: int, address: str, label: str, chains: list[str]) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                insert into monitors(user_id, address, label, chains_json, active, created_at)
                values (?, ?, ?, ?, 1, ?)
                """,
                (user_id, address, label, json.dumps(chains), int(time.time())),
            )
            return int(cur.lastrowid)

    def list_monitors(self, user_id: int | None = None, active_only: bool = False) -> list[dict[str, Any]]:
        query = "select * from monitors"
        filters: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            filters.append("user_id=?")
            params.append(user_id)
        if active_only:
            filters.append("active=1")
        if filters:
            query += " where " + " and ".join(filters)
        query += " order by id desc"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._monitor_dict(row) for row in rows]

    def update_monitor(self, user_id: int, monitor_id: int, active: bool, chains: list[str]) -> None:
        with self.connect() as conn:
            conn.execute(
                "update monitors set active=?, chains_json=? where id=? and user_id=?",
                (int(active), json.dumps(chains), monitor_id, user_id),
            )

    def delete_monitor(self, user_id: int, monitor_id: int) -> None:
        with self.connect() as conn:
            conn.execute("delete from monitors where id=? and user_id=?", (monitor_id, user_id))

    def get_chain_state(self, chain_key: str) -> int | None:
        with self.connect() as conn:
            row = conn.execute(
                "select last_block from chain_state where chain_key=?",
                (chain_key,),
            ).fetchone()
            return int(row["last_block"]) if row else None

    def set_chain_state(self, chain_key: str, last_block: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into chain_state(chain_key, last_block) values (?, ?)
                on conflict(chain_key) do update set last_block=excluded.last_block
                """,
                (chain_key, last_block),
            )

    def save_event(self, event: dict[str, Any]) -> bool:
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    insert into events(user_id, monitor_id, chain_key, event_key, tx_hash,
                      block_number, watched_address, action, direction, summary, details_json,
                      created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["user_id"],
                        event["monitor_id"],
                        event["chain_key"],
                        event["event_key"],
                        event["tx_hash"],
                        event["block_number"],
                        event["watched_address"],
                        event["action"],
                        event["direction"],
                        event["summary"],
                        json.dumps(event["details"]),
                        int(time.time()),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_events(self, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from events where user_id=? order by id desc limit ?",
                (user_id, limit),
            ).fetchall()
        return [self._event_dict(row) for row in rows]

    @staticmethod
    def _monitor_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["chains"] = json.loads(data.pop("chains_json"))
        data["active"] = bool(data["active"])
        return data

    @staticmethod
    def _event_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["details"] = json.loads(data.pop("details_json"))
        return data

