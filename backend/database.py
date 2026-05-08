import os
import time
from contextlib import contextmanager

_DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)

_PG = bool(_DATABASE_URL)
_PH = '%s' if _PG else '?'

if _PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3
    _DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timetracker.db')


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
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _fetchone(conn, sql, params=()):
    if _PG:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _exec(conn, sql, params=()):
    if _PG:
        conn.cursor().execute(sql, params)
    else:
        conn.execute(sql, params)


# ── schema ─────────────────────────────────────────────────────────────────

def init_db():
    with _conn() as conn:
        if _PG:
            _exec(conn, '''
                CREATE TABLE IF NOT EXISTS time_entries (
                    id          BIGSERIAL        PRIMARY KEY,
                    name        TEXT             NOT NULL,
                    type        TEXT             NOT NULL,
                    device      TEXT             NOT NULL DEFAULT 'unknown',
                    url         TEXT,
                    start_time  DOUBLE PRECISION NOT NULL,
                    end_time    DOUBLE PRECISION,
                    duration    DOUBLE PRECISION DEFAULT 0
                )
            ''')
            # Migration: add device column to existing tables
            _exec(conn, '''
                ALTER TABLE time_entries
                ADD COLUMN IF NOT EXISTS device TEXT NOT NULL DEFAULT 'unknown'
            ''')
            _exec(conn, 'CREATE INDEX IF NOT EXISTS idx_start  ON time_entries(start_time)')
            _exec(conn, 'CREATE INDEX IF NOT EXISTS idx_type   ON time_entries(type)')
            _exec(conn, 'CREATE INDEX IF NOT EXISTS idx_device ON time_entries(device)')
        else:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS time_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    type        TEXT    NOT NULL,
                    device      TEXT    NOT NULL DEFAULT 'unknown',
                    url         TEXT,
                    start_time  REAL    NOT NULL,
                    end_time    REAL,
                    duration    REAL    DEFAULT 0
                )
            ''')
            # Migration for existing SQLite tables
            try:
                conn.execute("ALTER TABLE time_entries ADD COLUMN device TEXT NOT NULL DEFAULT 'unknown'")
            except Exception:
                pass  # column already exists
            conn.execute('CREATE INDEX IF NOT EXISTS idx_start  ON time_entries(start_time)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_type   ON time_entries(type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_device ON time_entries(device)')


# ── writes ─────────────────────────────────────────────────────────────────

def insert_entry(name, entry_type, device='unknown', url=None):
    start = time.time()
    sql = (f'INSERT INTO time_entries (name, type, device, url, start_time, duration) '
           f'VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},0)')
    with _conn() as conn:
        if _PG:
            cur = conn.cursor()
            cur.execute(sql + ' RETURNING id', (name, entry_type, device, url, start))
            row_id = cur.fetchone()['id']
        else:
            row_id = conn.execute(sql, (name, entry_type, device, url, start)).lastrowid
    return row_id, start


def finalize_entry(entry_id, start_time):
    end = time.time()
    sql = f'UPDATE time_entries SET end_time={_PH}, duration={_PH} WHERE id={_PH}'
    with _conn() as conn:
        _exec(conn, sql, (end, end - start_time, entry_id))


def _insert_complete(name, entry_type, device, url, start_time, end_time):
    duration = end_time - start_time
    if duration < 1:
        return
    sql = (f'INSERT INTO time_entries (name, type, device, url, start_time, end_time, duration) '
           f'VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})')
    with _conn() as conn:
        _exec(conn, sql, (name, entry_type, device, url, start_time, end_time, duration))


def add_tab_entry(name, url, start_time, end_time, device='unknown'):
    if end_time - start_time < 2:
        return
    _insert_complete(name, 'tab', device, url, start_time, end_time)


def add_app_entry(name, start_time, end_time, device='unknown'):
    _insert_complete(name, 'app', device, None, start_time, end_time)


# ── reads ──────────────────────────────────────────────────────────────────

def _period_since(period):
    spans = {'day': 86400, 'week': 604800, 'month': 2592000, 'year': 31536000}
    return time.time() - spans.get(period, 86400)


def _device_clause(device):
    """Returns (sql_fragment, params_list) for optional device filter."""
    if device:
        return f'AND device = {_PH}', [device]
    return '', []


def get_devices():
    sql = "SELECT DISTINCT device FROM time_entries WHERE device != 'unknown' ORDER BY device"
    with _conn() as conn:
        rows = _fetchall(conn, sql)
    return [r['device'] for r in rows]


def get_stats(period, device=None):
    since = _period_since(period)
    dc, dp = _device_clause(device)
    sql = f'''
        SELECT name, type, MAX(url) AS url,
               SUM(duration) AS total_seconds,
               COUNT(*)      AS sessions
        FROM time_entries
        WHERE start_time >= {_PH} AND end_time IS NOT NULL {dc}
        GROUP BY name, type
        ORDER BY total_seconds DESC
    '''
    with _conn() as conn:
        return _fetchall(conn, sql, [since] + dp)


def get_hourly_breakdown(period, device=None):
    since = _period_since(period)
    bucket = 3600 if period == 'day' else 86400
    dc, dp = _device_clause(device)
    sql = f'''
        SELECT CAST((start_time - {_PH}) / {_PH} AS INTEGER) AS bucket,
               type,
               SUM(duration) AS total_seconds
        FROM time_entries
        WHERE start_time >= {_PH} AND end_time IS NOT NULL {dc}
        GROUP BY bucket, type
        ORDER BY bucket
    '''
    with _conn() as conn:
        return _fetchall(conn, sql, [since, bucket, since] + dp)


def get_total_today(device=None):
    since = _period_since('day')
    dc, dp = _device_clause(device)
    sql = (f'SELECT COALESCE(SUM(duration),0) AS t FROM time_entries '
           f'WHERE start_time>={_PH} AND end_time IS NOT NULL {dc}')
    with _conn() as conn:
        row = _fetchone(conn, sql, [since] + dp)
    return row['t'] if row else 0
