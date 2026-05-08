import os
import time
from contextlib import contextmanager

# ── backend selection ──────────────────────────────────────────────────────
# Set DATABASE_URL env var to a postgres:// or postgresql:// URL to use
# PostgreSQL (cloud).  Without it, falls back to local SQLite.

_DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)

_PG = bool(_DATABASE_URL)
_PH = '%s' if _PG else '?'   # SQL placeholder

if _PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    _DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timetracker.db')


# ── connection context manager ─────────────────────────────────────────────

@contextmanager
def _conn():
    if _PG:
        conn = psycopg2.connect(_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _cur(conn):
    return conn.cursor() if _PG else conn


def _fetchall(conn, sql, params=()):
    if _PG:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    else:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _fetchone(conn, sql, params=()):
    if _PG:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    else:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


# ── schema ─────────────────────────────────────────────────────────────────

def init_db():
    with _conn() as conn:
        if _PG:
            _cur(conn).execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    id          BIGSERIAL PRIMARY KEY,
                    name        TEXT             NOT NULL,
                    type        TEXT             NOT NULL,
                    url         TEXT,
                    start_time  DOUBLE PRECISION NOT NULL,
                    end_time    DOUBLE PRECISION,
                    duration    DOUBLE PRECISION DEFAULT 0
                )
            ''')
            _cur(conn).execute('CREATE INDEX IF NOT EXISTS idx_start ON time_entries(start_time)')
            _cur(conn).execute('CREATE INDEX IF NOT EXISTS idx_type  ON time_entries(type)')
        else:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    type        TEXT NOT NULL,
                    url         TEXT,
                    start_time  REAL NOT NULL,
                    end_time    REAL,
                    duration    REAL DEFAULT 0
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_start ON time_entries(start_time)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_type  ON time_entries(type)')


# ── write helpers ──────────────────────────────────────────────────────────

def insert_entry(name, entry_type, url=None):
    """Insert an open-ended entry (local tracking only). Returns (id, start_time)."""
    start = time.time()
    sql = f'INSERT INTO time_entries (name, type, url, start_time, duration) VALUES ({_PH},{_PH},{_PH},{_PH},0)'
    with _conn() as conn:
        if _PG:
            cur = conn.cursor()
            cur.execute(sql + ' RETURNING id', (name, entry_type, url, start))
            row_id = cur.fetchone()['id']
        else:
            row_id = conn.execute(sql, (name, entry_type, url, start)).lastrowid
    return row_id, start


def finalize_entry(entry_id, start_time):
    """Close an open entry by id (local tracking only)."""
    end = time.time()
    sql = f'UPDATE time_entries SET end_time={_PH}, duration={_PH} WHERE id={_PH}'
    with _conn() as conn:
        if _PG:
            _cur(conn).execute(sql, (end, end - start_time, entry_id))
        else:
            conn.execute(sql, (end, end - start_time, entry_id))


def _insert_complete(name, entry_type, url, start_time, end_time):
    duration = end_time - start_time
    if duration < 1:
        return
    sql = (f'INSERT INTO time_entries (name, type, url, start_time, end_time, duration) '
           f'VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})')
    with _conn() as conn:
        if _PG:
            _cur(conn).execute(sql, (name, entry_type, url, start_time, end_time, duration))
        else:
            conn.execute(sql, (name, entry_type, url, start_time, end_time, duration))


def add_tab_entry(name, url, start_time, end_time):
    if end_time - start_time < 2:
        return
    _insert_complete(name, 'tab', url, start_time, end_time)


def add_app_entry(name, start_time, end_time):
    _insert_complete(name, 'app', None, start_time, end_time)


# ── read helpers ───────────────────────────────────────────────────────────

def _period_since(period):
    spans = {'day': 86400, 'week': 604800, 'month': 2592000, 'year': 31536000}
    return time.time() - spans.get(period, 86400)


def get_stats(period):
    since = _period_since(period)
    sql = f'''
        SELECT name, type, url,
               SUM(duration) AS total_seconds,
               COUNT(*)      AS sessions
        FROM time_entries
        WHERE start_time >= {_PH} AND end_time IS NOT NULL
        GROUP BY name, type
        ORDER BY total_seconds DESC
    '''
    with _conn() as conn:
        return _fetchall(conn, sql, (since,))


def get_hourly_breakdown(period):
    since = _period_since(period)
    bucket = 3600 if period == 'day' else 86400
    sql = f'''
        SELECT CAST((start_time - {_PH}) / {_PH} AS INTEGER) AS bucket,
               type,
               SUM(duration) AS total_seconds
        FROM time_entries
        WHERE start_time >= {_PH} AND end_time IS NOT NULL
        GROUP BY bucket, type
        ORDER BY bucket
    '''
    with _conn() as conn:
        return _fetchall(conn, sql, (since, bucket, since))


def get_total_today():
    since = _period_since('day')
    sql = f'SELECT COALESCE(SUM(duration),0) AS t FROM time_entries WHERE start_time>={_PH} AND end_time IS NOT NULL'
    with _conn() as conn:
        row = _fetchone(conn, sql, (since,))
    return row['t'] if row else 0
