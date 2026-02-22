import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from .config import settings

def dsn() -> str:
    return (
        f"host={settings.POSTGRES_HOST} port={settings.POSTGRES_PORT} "
        f"dbname={settings.POSTGRES_DB} user={settings.POSTGRES_USER} password={settings.POSTGRES_PASSWORD}"
    )

@contextmanager
def conn_cursor(dict_cursor: bool = True):
    conn = psycopg2.connect(dsn())
    try:
        cur_factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cur_factory)
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def fetchone(sql: str, params=None):
    with conn_cursor() as (_, cur):
        cur.execute(sql, params or ())
        return cur.fetchone()

def fetchall(sql: str, params=None):
    with conn_cursor() as (_, cur):
        cur.execute(sql, params or ())
        return cur.fetchall()

def execute(sql: str, params=None):
    with conn_cursor(dict_cursor=False) as (_, cur):
        cur.execute(sql, params or ())
