"""SQLite: login records (DESIGN §2), and an index derived from the stores.

`logins`, `addresses` and `preexisting` are the records §10 needs.
`mentions` is only an index — which stores contain which address — kept so a
reader need not open every store; it can be rebuilt from the stores.
"""

import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS logins (
    username  TEXT PRIMARY KEY,
    password  TEXT NOT NULL,
    created   REAL NOT NULL
);
-- Every address ever registered. Never deleted: an address is not reused.
CREATE TABLE IF NOT EXISTS addresses (
    address     TEXT PRIMARY KEY,
    owner       TEXT NOT NULL,
    registered  REAL NOT NULL
);
-- What already sat below an address in another store when it was
-- registered. Never counts as shared (DESIGN §10).
CREATE TABLE IF NOT EXISTS preexisting (
    address  TEXT NOT NULL,
    store    TEXT NOT NULL,
    node     TEXT NOT NULL,
    PRIMARY KEY (address, store, node)
);
CREATE TABLE IF NOT EXISTS mentions (
    address  TEXT NOT NULL,
    store    TEXT NOT NULL,
    PRIMARY KEY (address, store)
);
CREATE INDEX IF NOT EXISTS mentions_store ON mentions(store);
"""


class Database:
    """One connection, serialized: the site's writes are tiny and rare."""

    def __init__(self, path):
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._con.executescript(SCHEMA)

    def query(self, sql, args=()):
        with self._lock:
            return self._con.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def write(self, sql, args=()):
        with self._lock:
            self._con.execute(sql, args)
            self._con.commit()

    def write_many(self, statements):
        with self._lock:
            for sql, args in statements:
                self._con.execute(sql, args)
            self._con.commit()


def now():
    return time.time()
