import sqlite3
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from config import Config

_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            alias_name TEXT,
            script_type TEXT NOT NULL,
            file_hash TEXT,
            status_load INTEGER NOT NULL DEFAULT 0,
            load_error_msg TEXT,
            status_last_run INTEGER NOT NULL DEFAULT 0,
            args_schema TEXT,
            notify_enabled INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            duration_ms INTEGER,
            status INTEGER NOT NULL,
            params_json TEXT,
            stdout_preview TEXT,
            stderr TEXT,
            output_file_url TEXT,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(script_id) REFERENCES scripts(id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS install_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            runtime TEXT NOT NULL,
            requested_list TEXT NOT NULL,
            conflict_list TEXT,
            log_text TEXT NOT NULL,
            status INTEGER NOT NULL,
            created_at DATETIME NOT NULL
        );
        """
    )

    conn.commit()

    # defaults
    set_setting("scan_interval", str(Config.SCAN_INTERVAL_SEC))
    set_setting("timeout_min", str(Config.TIMEOUT_MIN))
    if get_setting("notify_url") is None and Config.DEFAULT_NOTIFY_URL:
        set_setting("notify_url", Config.DEFAULT_NOTIFY_URL)
    if get_setting("script_log_retention_days") is None:
        set_setting("script_log_retention_days", "7")
    if get_setting("gateway_log_retention_days") is None:
        set_setting("gateway_log_retention_days", "7")


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_setting(key: str) -> Optional[str]:
    conn = get_conn()
    cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


# Scripts CRUD

def upsert_script(
    filename: str,
    script_type: str,
    file_hash: str,
    status_load: int,
    load_error_msg: Optional[str],
    args_schema: Optional[str],
):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cur = conn.execute(
        "SELECT id FROM scripts WHERE filename=?", (filename,)
    )
    row = cur.fetchone()
    if row:
        conn.execute(
            """
            UPDATE scripts SET file_hash=?, status_load=?, load_error_msg=?,
                   args_schema=?, updated_at=?
            WHERE filename=?
            """,
            (file_hash, status_load, load_error_msg, args_schema, now, filename),
        )
    else:
        conn.execute(
            """
            INSERT INTO scripts(filename, alias_name, script_type, file_hash,
                                status_load, load_error_msg, status_last_run,
                                args_schema, notify_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?)
            """,
            (filename, filename, script_type, file_hash, status_load, load_error_msg, args_schema, now, now),
        )
    conn.commit()


def list_scripts(
    script_type: Optional[str], search: Optional[str], page: int, page_size: int
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_conn()
    params: List[Any] = []
    where = []
    if script_type:
        where.append("script_type=?")
        params.append(script_type)
    if search:
        where.append("(filename LIKE ? OR alias_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM scripts{where_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT s.*, 
            (
                SELECT r.duration_ms FROM runs r
                WHERE r.script_id = s.id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) AS last_duration_ms,
            (
                SELECT COUNT(*) FROM runs r
                WHERE r.script_id = s.id
            ) AS run_count,
            (
                SELECT r.finished_at FROM runs r
                WHERE r.script_id = s.id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) AS last_run_at
        FROM scripts s
        {where_sql}
        ORDER BY s.updated_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    ).fetchall()
    return [dict(r) for r in rows], count


def get_script_by_id(script_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM scripts WHERE id=?", (script_id,)).fetchone()
    return dict(row) if row else None


def update_alias(script_id: int, alias: str):
    conn = get_conn()
    conn.execute(
        "UPDATE scripts SET alias_name=?, updated_at=? WHERE id=?",
        (alias, time.strftime("%Y-%m-%d %H:%M:%S"), script_id),
    )
    conn.commit()


def update_last_run(script_id: int, status_last_run: int):
    conn = get_conn()
    conn.execute(
        "UPDATE scripts SET status_last_run=?, updated_at=? WHERE id=?",
        (status_last_run, time.strftime("%Y-%m-%d %H:%M:%S"), script_id),
    )
    conn.commit()


def insert_run(
    script_id: int,
    started_at: str,
    finished_at: Optional[str],
    duration_ms: Optional[int],
    status: int,
    params_json: Optional[str],
    stdout_preview: Optional[str],
    stderr: Optional[str],
    output_file_url: Optional[str],
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO runs(script_id, started_at, finished_at, duration_ms, status,
                         params_json, stdout_preview, stderr, output_file_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            script_id,
            started_at,
            finished_at,
            duration_ms,
            status,
            params_json,
            stdout_preview,
            stderr,
            output_file_url,
            time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    return cur.lastrowid
