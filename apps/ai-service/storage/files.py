from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Protocol


class StorageUnavailableError(RuntimeError):
    """The document store cannot currently serve the requested object."""


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
            from urllib3 import PoolManager, Retry, Timeout
        except ImportError as exc:
            raise RuntimeError("minio is required for MINIO storage") from exc
        self.bucket = bucket
        host = endpoint.removeprefix("http://").removeprefix("https://")
        self.client = Minio(
            host, access_key=access_key, secret_key=secret_key, secure=secure,
            # The SDK default can wait minutes per connection attempt. Bound
            # failed connects so indexing can report a storage failure promptly.
            http_client=PoolManager(
                timeout=Timeout(connect=5, read=60),
                retries=Retry(total=2, connect=2, read=0, backoff_factor=0.5),
            ),
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
        from minio.error import S3Error
        from urllib3.exceptions import HTTPError

        def read() -> bytes:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await asyncio.to_thread(read)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise FileNotFoundError("资料原文件不存在，请重新上传") from exc
            raise StorageUnavailableError("无法读取资料原文件，请检查文件存储服务的权限与存储桶配置") from exc
        except HTTPError as exc:
            raise StorageUnavailableError("文件存储服务连接失败，请恢复连接后重新索引") from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.remove_object, self.bucket, key)
