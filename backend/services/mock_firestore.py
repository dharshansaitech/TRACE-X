# backend/services/mock_firestore.py
"""In-memory drop-in replacement for `google.cloud.firestore.AsyncClient`.

Implements only the surface used by `services.firestore_service.FirestoreService`:
`.collection(name)`, `.document(id)`, `.get()`, `.set(data, merge=)`, `.delete()`,
`.where()`, `.order_by()`, `.limit()`, async `.stream()`.

Used as a fallback when no GCP credentials are available (demo / local dev mode),
so the real FirestoreService business logic runs unchanged against an in-memory store.
"""
from __future__ import annotations

import copy
import uuid
from collections import defaultdict
from typing import Any, AsyncIterator, Callable

from google.cloud import firestore as _firestore

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b,
    "array_contains": lambda a, b: b in (a or []),
}


class _DocSnapshot:
    def __init__(self, doc_id: str, data: dict | None) -> None:
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict | None:
        return copy.deepcopy(self._data) if self._data is not None else None


class _DocumentReference:
    def __init__(self, client: "MockFirestoreClient", collection: str, doc_id: str) -> None:
        self._client = client
        self._collection = collection
        self.id = doc_id

    async def get(self) -> _DocSnapshot:
        data = self._client._store[self._collection].get(self.id)
        return _DocSnapshot(self.id, data)

    async def set(self, data: dict, merge: bool = False) -> None:
        col = self._client._store[self._collection]
        snapshot = copy.deepcopy(data)
        if merge and self.id in col:
            col[self.id] = {**col[self.id], **snapshot}
        else:
            col[self.id] = snapshot

    async def delete(self) -> None:
        self._client._store[self._collection].pop(self.id, None)


class CollectionReference:
    def __init__(
        self,
        client: "MockFirestoreClient",
        collection: str,
        filters: list[tuple[str, str, Any]] | None = None,
        orders: list[tuple[str, str]] | None = None,
        limit_n: int | None = None,
    ) -> None:
        self._client = client
        self._collection = collection
        self._filters = filters or []
        self._orders = orders or []
        self._limit = limit_n

    def document(self, doc_id: str | None = None) -> _DocumentReference:
        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return _DocumentReference(self._client, self._collection, doc_id)

    def where(self, field: str, op: str, value: Any) -> "CollectionReference":
        return CollectionReference(
            self._client, self._collection, self._filters + [(field, op, value)], self._orders, self._limit
        )

    def order_by(self, field: str, direction: str = _firestore.Query.ASCENDING) -> "CollectionReference":
        return CollectionReference(
            self._client, self._collection, self._filters, self._orders + [(field, direction)], self._limit
        )

    def limit(self, n: int) -> "CollectionReference":
        return CollectionReference(self._client, self._collection, self._filters, self._orders, n)

    async def stream(self) -> AsyncIterator[_DocSnapshot]:
        col = self._client._store[self._collection]
        docs: list[tuple[str, dict]] = [(doc_id, copy.deepcopy(data)) for doc_id, data in col.items()]

        for field, op, value in self._filters:
            fn = _OPS[op]
            docs = [(doc_id, data) for doc_id, data in docs if fn(data.get(field), value)]

        for field, direction in reversed(self._orders):
            reverse = direction == _firestore.Query.DESCENDING
            docs.sort(key=lambda kv: _sort_key(kv[1].get(field)), reverse=reverse)

        if self._limit is not None:
            docs = docs[: self._limit]

        for doc_id, data in docs:
            yield _DocSnapshot(doc_id, data)


def _sort_key(value: Any) -> Any:
    return "" if value is None else value


class MockFirestoreClient:
    """In-memory Firestore client. Data is lost on process restart."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict]] = defaultdict(dict)

    def collection(self, name: str) -> CollectionReference:
        return CollectionReference(self, name)
