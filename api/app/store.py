"""Tiny transactional storage interface with two backends:

- FirestoreStore: production (Firebase Admin SDK; bypasses security rules by design).
- MemoryStore: tests and local demos without credentials.

All business logic (clustering, rate limits, status changes) is written once against `Tx`,
so the tests exercise exactly the code that runs in production.
"""
from __future__ import annotations

import copy
import threading
from typing import Any, Callable, Protocol

Filter = tuple[str, str, Any]  # (field, "==" | "in" | "array_contains_any", value)


class Tx(Protocol):
    def get(self, coll: str, doc_id: str) -> dict | None: ...
    def query(self, coll: str, filters: list[Filter]) -> list[tuple[str, dict]]: ...
    def set(self, coll: str, doc_id: str, data: dict) -> None: ...
    def update(self, coll: str, doc_id: str, data: dict) -> None: ...


class Store(Protocol):
    def run(self, fn: Callable[[Tx], Any]) -> Any: ...
    def get(self, coll: str, doc_id: str) -> dict | None: ...


# ---------------------------------------------------------------------------------------------
class _MemTx:
    def __init__(self, data: dict):
        self._data = data
        self._writes: list[tuple[str, str, str, dict]] = []

    def get(self, coll, doc_id):
        d = self._data.get(coll, {}).get(doc_id)
        return copy.deepcopy(d) if d is not None else None

    def query(self, coll, filters):
        out = []
        for doc_id, d in self._data.get(coll, {}).items():
            ok = True
            for field, op, value in filters:
                v = d.get(field)
                if op == "==" and v != value:
                    ok = False
                elif op == "in" and v not in value:
                    ok = False
                elif op == "array_contains_any" and not set(v or []) & set(value):
                    ok = False
            if ok:
                out.append((doc_id, copy.deepcopy(d)))
        return out

    def set(self, coll, doc_id, data):
        self._writes.append(("set", coll, doc_id, copy.deepcopy(data)))

    def update(self, coll, doc_id, data):
        self._writes.append(("update", coll, doc_id, copy.deepcopy(data)))

    def commit(self):
        for op, coll, doc_id, data in self._writes:
            c = self._data.setdefault(coll, {})
            if op == "set":
                c[doc_id] = data
            else:
                if doc_id not in c:
                    raise KeyError(f"{coll}/{doc_id} not found")
                c[doc_id].update(data)


class MemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}
        self._lock = threading.Lock()

    def run(self, fn):
        with self._lock:  # serialisable, like a Firestore transaction
            tx = _MemTx(self.data)
            result = fn(tx)
            tx.commit()
            return result

    def get(self, coll, doc_id):
        d = self.data.get(coll, {}).get(doc_id)
        return copy.deepcopy(d) if d is not None else None


# ---------------------------------------------------------------------------------------------
class _FsTx:
    def __init__(self, client, transaction):
        self._c = client
        self._t = transaction

    def get(self, coll, doc_id):
        snap = self._c.collection(coll).document(doc_id).get(transaction=self._t)
        return snap.to_dict() if snap.exists else None

    def query(self, coll, filters):
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self._c.collection(coll)
        for field, op, value in filters:
            q = q.where(filter=FieldFilter(field, op, value))
        return [(s.id, s.to_dict()) for s in self._t.get(q)]

    def set(self, coll, doc_id, data):
        self._t.set(self._c.collection(coll).document(doc_id), data)

    def update(self, coll, doc_id, data):
        self._t.update(self._c.collection(coll).document(doc_id), data)


class FirestoreStore:
    def __init__(self, client):
        self._c = client

    def run(self, fn):
        from google.cloud import firestore

        @firestore.transactional
        def _inner(transaction):
            return fn(_FsTx(self._c, transaction))

        return _inner(self._c.transaction(max_attempts=5))

    def get(self, coll, doc_id):
        snap = self._c.collection(coll).document(doc_id).get()
        return snap.to_dict() if snap.exists else None
