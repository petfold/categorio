"""One OntoDAG `rs:` store per account (DESIGN §2).

Each store is a record-store directory: content-addressed blobs and a root
pointer, so every commit is a version and undo/redo move the pointer, as
`odag undo` does. Stores are held in memory once loaded; every write goes
through `edit`, which commits and then keeps the derived records in step:
the `mentions` index, and the registration of new own addresses (§10).
"""

import os
import threading

import recordstore as rs
from ontodag.eager import EagerOntoDAG

from categorio import names, ontology
from categorio.db import now


class Stores:
    def __init__(self, directory, db):
        self.directory = directory
        self.db = db
        self._dags = {}
        self._lock = threading.RLock()
        os.makedirs(directory, exist_ok=True)

    # ---- opening -------------------------------------------------------------

    def _path(self, user):
        if not names.USERNAME.match(user):
            raise ValueError(f"bad username {user!r}")
        return os.path.join(self.directory, user)

    def _record_store(self, user):
        path = self._path(user)
        return rs.RecordStore(rs.DirBytesStore(os.path.join(path, "blobs")),
                              pointer=rs.FilePointer(os.path.join(path, "root")))

    def exists(self, user):
        return os.path.exists(os.path.join(self._path(user), "root"))

    def get(self, user):
        """The account's store as a live DAG. Read it, never mutate it here."""
        with self._lock:
            dag = self._dags.get(user)
            if dag is None:
                dag = EagerOntoDAG(self._record_store(user))
                self._dags[user] = dag
            return dag

    def revision(self, user):
        return self.get(user).base_root

    def _forget(self, user):
        with self._lock:
            self._dags.pop(user, None)

    # ---- writing -------------------------------------------------------------

    def create(self, user):
        """A new store: the prelude (so dimension values work) and the
        account's own address."""
        with self._lock:
            dag = EagerOntoDAG(self._record_store(user))
            dag.merge(ontology.prelude())
            dag.put(names.address(user), [])
            dag.commit(message="created")
            self._dags[user] = dag
        self.register(names.address(user), user)
        self._reindex(user)

    def edit(self, user, change, message):
        """Apply `change(dag)` and commit. On any error the in-memory copy,
        which may be half-changed, is dropped and the last commit wins."""
        with self._lock:
            dag = self.get(user)
            try:
                result = change(dag)
                dag.commit(message=message)
            except Exception:
                self._forget(user)
                raise
        self._reindex(user)
        return result

    def history(self, user):
        store = self._record_store(user)
        status = store.status()
        return store.history(), status

    def step(self, user, direction):
        """Undo (-1) or redo (+1). Returns the new root or None."""
        with self._lock:
            store = self._record_store(user)
            root = store.undo() if direction < 0 else store.redo()
            self._forget(user)
        if root is not None:
            self._reindex(user)
        return root

    # ---- derived records -----------------------------------------------------

    def _reindex(self, user):
        """Keep `mentions` in step with the store, and register any new
        address of the account's own that has appeared in it."""
        dag = self.get(user)
        present = sorted(n for n in dag.nodes if names.parse_address(n))
        self.db.write_many(
            [("DELETE FROM mentions WHERE store = ?", (user,))]
            + [("INSERT INTO mentions (address, store) VALUES (?, ?)", (a, user))
               for a in present])
        for address in present:
            if names.owner_of(address) == user and not self.registered(address):
                self.register(address, user)

    def registered(self, address):
        return self.db.one("SELECT owner FROM addresses WHERE address = ?", (address,))

    def register(self, address, owner):
        """Register an address. Whatever other stores already hold below it
        is recorded as preexisting and never counts as shared (§10)."""
        rows = [("INSERT OR IGNORE INTO addresses (address, owner, registered) VALUES (?, ?, ?)",
                 (address, owner, now()))]
        for (store,) in self.db.query(
                "SELECT store FROM mentions WHERE address = ? AND store != ?", (address, owner)):
            for node in ontology.cone(self.get(store), address):
                rows.append(("INSERT OR IGNORE INTO preexisting (address, store, node) "
                             "VALUES (?, ?, ?)", (address, store, node)))
        self.db.write_many(rows)

    def mentioning(self, address):
        return [r["store"] for r in self.db.query(
            "SELECT store FROM mentions WHERE address = ?", (address,))]

    def preexisting(self, address, store):
        return frozenset(r["node"] for r in self.db.query(
            "SELECT node FROM preexisting WHERE address = ? AND store = ?", (address, store)))
