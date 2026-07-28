"""
SkillSwap NSU  —  db.py
Thin wrapper around mysql-connector-python.

No ORM is used anywhere in this project. Every statement is hand written
SQL and every value is passed as a parameter (%s), which is both the point
of a Database Systems Lab project and the defence against SQL injection.
"""

import contextlib
import datetime

import mysql.connector
from flask import current_app, g


# ------------------------------------------------------------------ connection
def get_db():
    """One connection per request, stored on Flask's request context."""
    if 'db' not in g:
        g.db = mysql.connector.connect(**current_app.config['DB'])
    return g.db


def close_db(_exc=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


# ------------------------------------------------------------------ reads
def query(sql, params=(), one=False):
    """
    SELECT -> list of dicts (or a single dict when one=True).

    `params or None` matters: the connector only interpolates when params is
    not None, and an empty tuple would still trigger it — which breaks any
    statement containing a literal %, such as DATE_FORMAT(d, '%Y-%m').
    """
    cur = get_db().cursor(dictionary=True)
    cur.execute(sql, params or None)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def scalar(sql, params=(), default=None):
    """SELECT that returns exactly one value."""
    cur = get_db().cursor()
    cur.execute(sql, params or None)
    row = cur.fetchone()
    cur.close()
    if row is None or row[0] is None:
        return default
    return row[0]


# ------------------------------------------------------------------ writes
def execute(sql, params=()):
    """
    One INSERT / UPDATE / DELETE wrapped in its own transaction.
    Returns (lastrowid, rowcount). Raises on failure after ROLLBACK.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or None)
        conn.commit()
        return cur.lastrowid, cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def execute_many(statements):
    """
    Several statements as ONE transaction — all of them commit, or none do.
    `statements` is a list of (sql, params) tuples.
    Returns the list of lastrowid values.
    """
    conn = get_db()
    cur = conn.cursor()
    ids = []
    try:
        for sql, params in statements:
            cur.execute(sql, params)
            ids.append(cur.lastrowid)
        conn.commit()
        return ids
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


@contextlib.contextmanager
def transaction():
    """
    START TRANSACTION ... COMMIT, with ROLLBACK on any exception.

        with transaction() as cur:
            cur.execute('INSERT INTO users ...', params)
            new_id = cur.lastrowid
            cur.execute('INSERT INTO userskills ...', (new_id, ...))
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ------------------------------------------------------------------ helpers
def time_to_str(value):
    """
    MySQL TIME comes back as datetime.timedelta from the connector.
    Normalise timedelta / time / str down to 'HH:MM'.
    """
    if value is None:
        return ''
    if isinstance(value, datetime.timedelta):
        total = int(value.total_seconds())
        return '%02d:%02d' % (total // 3600, (total % 3600) // 60)
    if isinstance(value, datetime.time):
        return value.strftime('%H:%M')
    return str(value)[:5]


def date_to_str(value):
    """DATE / DATETIME / str -> 'YYYY-MM-DD'."""
    if value is None:
        return ''
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]
