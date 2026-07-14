"""Media storage behind a thin adapter.

Alpha 0.1 stopgap: bytes live in the OceanBase `media_blob` table (Substrait injects no
object store). The interface matches an S3-style store so the real bucket drops in later
with no schema or call-site change — every *_ref column holds an opaque key.

    key = await store.put(data, content_type)   # returns the ref to persist
    data, content_type = await store.get(key)
    url = store.url(key)                         # relative URL the frontend can fetch
"""
import uuid
from abc import ABC, abstractmethod

import db


class StorageAdapter(ABC):
    @abstractmethod
    async def put(self, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    async def get(self, key: str) -> tuple[bytes, str] | None: ...

    def url(self, key: str) -> str:
        return f"/api/media/{key}"


class BlobStorage(StorageAdapter):
    """In-DB LONGBLOB. Fine at pilot volume; swap for S3 before production scale."""

    async def put(self, data: bytes, content_type: str) -> str:
        key = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO media_blob (id, content_type, byte_size, data) VALUES (%s, %s, %s, %s)",
            (key, content_type, len(data), data),
        )
        return key

    async def get(self, key: str) -> tuple[bytes, str] | None:
        row = await db.fetch_one(
            "SELECT data, content_type FROM media_blob WHERE id = %s", (key,)
        )
        if not row:
            return None
        return row["data"], row["content_type"]


# Future: class S3Storage(StorageAdapter) issuing presigned URLs from store.url().
store: StorageAdapter = BlobStorage()
