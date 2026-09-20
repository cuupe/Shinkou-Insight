from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class LocalFileStorage:
    """Content-addressed local storage with path traversal protection."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("storage key escapes storage root")
        return candidate

    async def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._resolve(key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)


class MinioFileStorage:
    """S3-compatible MinIO adapter; blocking SDK calls run off the event loop."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ):
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError("minio is required for MINIO storage") from exc
        self.bucket = bucket
        host = endpoint.removeprefix("http://").removeprefix("https://")
        self.client = Minio(
            host, access_key=access_key, secret_key=secret_key, secure=secure
        )

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type="application/octet-stream",
        )

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.remove_object, self.bucket, key)
