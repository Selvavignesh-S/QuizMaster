import re
import sqlite3
import psycopg2
from contextlib import contextmanager
from config import Config

class SQLiteCursorWrapper:
    """Wrapper around sqlite3 cursor to normalize SQL syntax (%s to ?, ANY(%s) handling, etc.)"""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        if not params:
            sql_mod = sql.replace("%s", "?")
            sql_mod = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s*days'", r"datetime('now', '-\1 days')", sql_mod, flags=re.IGNORECASE)
            sql_mod = re.sub(r"NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s*days'", r"datetime('now', '-\1 days')", sql_mod, flags=re.IGNORECASE)
            sql_mod = re.sub(r"\bNOW\(\)", "CURRENT_TIMESTAMP", sql_mod, flags=re.IGNORECASE)
            return self._cursor.execute(sql_mod)

        params_list = list(params) if isinstance(params, (list, tuple)) else [params]
        sql_parts = sql.split('%s')

        if len(sql_parts) - 1 != len(params_list):
            sql_mod = sql.replace("%s", "?")
            return self._cursor.execute(sql_mod, params)

        new_sql = sql_parts[0]
        new_params = []

        for i, param in enumerate(params_list):
            part = sql_parts[i + 1]
            check_text = new_sql.rstrip().upper()
            if "ANY(" in check_text or "ANY (" in check_text:
                eq_idx = new_sql.rfind("=")
                in_idx = new_sql.upper().rfind("IN ")
                idx = max(eq_idx, in_idx)
                if idx != -1:
                    new_sql = new_sql[:idx]
                    items = list(param) if isinstance(param, (list, tuple, set)) else [param]
                    if not items:
                        new_sql += "IN (NULL)"
                    else:
                        placeholders = ",".join(["?"] * len(items))
                        new_sql += f"IN ({placeholders})"
                        new_params.extend(items)
                    if part.lstrip().startswith(")"):
                        part = part.lstrip()[1:]
            else:
                new_sql += "?"
                new_params.append(param)
            new_sql += part

        new_sql = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s*days'", r"datetime('now', '-\1 days')", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"NOW\(\)\s*-\s*INTERVAL\s*'(\d+)\s*days'", r"datetime('now', '-\1 days')", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\bNOW\(\)", "CURRENT_TIMESTAMP", new_sql, flags=re.IGNORECASE)

        return self._cursor.execute(new_sql, new_params)
        # Replace NOW() and CURRENT_DATE with datetime expressions for SQLite
        sql_mod = re.sub(r'\bNOW\(\)', "CURRENT_TIMESTAMP", sql_mod, flags=re.IGNORECASE)
        sql_mod = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'(\d+)\s*days'", r"datetime('now', '-\1 days')", sql_mod, flags=re.IGNORECASE)
        
        return self._cursor.execute(sql_mod, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class SQLiteConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SQLiteCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_raw_connection(db_engine=None, sqlite_path=None):
    engine = db_engine or Config.DB_ENGINE
    if engine == 'sqlite':
        path = sqlite_path or Config.SQLITE_PATH
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = None
        return SQLiteConnWrapper(conn)
    else:
        return psycopg2.connect(
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )

def get_db_connection():
    """Returns database connection based on Config.DB_ENGINE ('sqlite' or 'postgres')."""
    engine = Config.DB_ENGINE.lower()
    if engine in ('postgres', 'postgresql'):
        try:
            return get_raw_connection('postgresql')
        except Exception as e:
            print(f"[Database Warning] Could not connect to PostgreSQL ({e}). Falling back to SQLite.")
            return get_raw_connection('sqlite')
    else:
        return get_raw_connection('sqlite')


@contextmanager
def db_session(commit=False):
    """
    Context manager for database sessions.
    Usage:
        with db_session(commit=True) as (conn, cur):
            cur.execute(...)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        yield conn, cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
