import sqlite3
import os
import time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timetracker.db')


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute('''
            CREATE TABLE IF NOT EXISTS time_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                type        TEXT    NOT NULL,
                url         TEXT,
                start_time  REAL    NOT NULL,
                end_time    REAL,
                duration    REAL    DEFAULT 0
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_start ON time_entries(start_time)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_type  ON time_entries(type)')


def insert_entry(name, entry_type, url=None):
    start = time.time()
    with _conn() as c:
        row_id = c.execute(
            'INSERT INTO time_entries (name, type, url, start_time, duration) VALUES (?,?,?,?,0)',
            (name, entry_type, url, start)
        ).lastrowid
    return row_id, start


def finalize_entry(entry_id, start_time):
    end = time.time()
    with _conn() as c:
        c.execute(
            'UPDATE time_entries SET end_time=?, duration=? WHERE id=?',
            (end, end - start_time, entry_id)
        )


def add_tab_entry(name, url, start_time, end_time):
    duration = end_time - start_time
    if duration < 2:
        return
    with _conn() as c:
        c.execute(
            'INSERT INTO time_entries (name, type, url, start_time, end_time, duration) VALUES (?,?,?,?,?,?)',
            (name, 'tab', url, start_time, end_time, duration)
        )


def _period_since(period):
    spans = {'day': 86400, 'week': 604800, 'month': 2592000, 'year': 31536000}
    return time.time() - spans.get(period, 86400)


def get_stats(period):
    since = _period_since(period)
    with _conn() as c:
        rows = c.execute('''
            SELECT name, type, url,
                   SUM(duration)  AS total_seconds,
                   COUNT(*)       AS sessions
            FROM time_entries
            WHERE start_time >= ? AND end_time IS NOT NULL
            GROUP BY name, type
            ORDER BY total_seconds DESC
        ''', (since,)).fetchall()
    return [dict(r) for r in rows]


def get_hourly_breakdown(period):
    since = _period_since(period)
    bucket = 3600 if period == 'day' else 86400
    with _conn() as c:
        rows = c.execute('''
            SELECT CAST((start_time - ?) / ? AS INTEGER) AS bucket,
                   type,
                   SUM(duration) AS total_seconds
            FROM time_entries
            WHERE start_time >= ? AND end_time IS NOT NULL
            GROUP BY bucket, type
            ORDER BY bucket
        ''', (since, bucket, since)).fetchall()
    return [dict(r) for r in rows]


def get_total_today():
    since = _period_since('day')
    with _conn() as c:
        row = c.execute(
            'SELECT COALESCE(SUM(duration),0) AS t FROM time_entries WHERE start_time>=? AND end_time IS NOT NULL',
            (since,)
        ).fetchone()
    return row['t'] if row else 0
