import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "requests.db"


def _get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                output_path TEXT NOT NULL,
                counts_json TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                processing_ms INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def insert_request(
    filename: str,
    output_path: str,
    counts: Dict[str, int],
    total_count: int,
    model_name: str,
    created_at: str,
    processing_ms: int,
    db_path: Path = DB_PATH,
) -> int:
    counts_json = json.dumps(counts, ensure_ascii=False)
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO requests (filename, output_path, counts_json, total_count, model_name, created_at, processing_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, output_path, counts_json, total_count, model_name, created_at, processing_ms),
        )
        conn.commit()
        return int(cur.lastrowid)


def fetch_recent(limit: int = 10, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_all(db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    with _get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def get_summary(db_path: Path = DB_PATH) -> Dict[str, Any]:
    with _get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total_requests,
                   COALESCE(SUM(total_count), 0) AS total_fruits,
                   COALESCE(AVG(total_count), 0) AS avg_per_request
            FROM requests
            """
        ).fetchone()
    return dict(row)


def get_counts_by_class(db_path: Path = DB_PATH) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for row in fetch_all(db_path):
        try:
            counts = json.loads(row["counts_json"])
        except json.JSONDecodeError:
            counts = {}
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + int(value)
    return totals
