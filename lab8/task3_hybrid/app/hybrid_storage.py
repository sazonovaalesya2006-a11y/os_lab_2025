"""
Менеджер гибридного хранилища (HOT + WARM + COLD).

Уровни:
  HOT  — локальный диск (быстро, дорого)
  WARM — MinIO bucket hybrid-warm (средне)
  COLD — MinIO bucket hybrid-cold (медленно, дёшево)

Политики миграции:
  HOT → WARM : если не читали N дней (по умолчанию 7)
  WARM → COLD: если не читали M дней (по умолчанию 30)
  COLD → HOT : при обращении (автоматический promote)
"""
import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class StorageTier(Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


@dataclass
class FileMetadata:
    filename: str
    tier: str          # "hot" | "warm" | "cold"
    size: int
    created_at: float
    last_accessed: float
    access_count: int
    checksum: str

    def to_dict(self):
        return asdict(self)


class HybridStorageManager:
    """Управляет тремя уровнями хранения."""

    def __init__(self,
                 hot_path: str = "hot_storage",
                 warm_bucket: str = "hybrid-warm",
                 cold_bucket: str = "hybrid-cold",
                 endpoint: str = "http://localhost:9000",
                 access_key: str = "minioadmin",
                 secret_key: str = "minioadmin123",
                 hot_to_warm_days: float = 7,
                 warm_to_cold_days: float = 30):
        self.hot_path = Path(hot_path)
        self.warm_bucket = warm_bucket
        self.cold_bucket = cold_bucket
        self.hot_to_warm_seconds = hot_to_warm_days * 86400
        self.warm_to_cold_seconds = warm_to_cold_days * 86400

        # Создаём локальную папку для HOT
        self.hot_path.mkdir(parents=True, exist_ok=True)

        # S3-клиент для WARM и COLD
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        # Убедимся, что bucket'ы созданы
        self._ensure_bucket(self.warm_bucket)
        self._ensure_bucket(self.cold_bucket)

        # Метаданные (в JSON-файле)
        self.metadata_path = Path("metadata.json")
        self.metadata: Dict[str, FileMetadata] = {}
        self._load_metadata()

    # ---------- Служебное ----------

    def _ensure_bucket(self, name: str):
        try:
            self.s3.head_bucket(Bucket=name)
        except ClientError:
            self.s3.create_bucket(Bucket=name)

    def _load_metadata(self):
        if self.metadata_path.exists():
            with open(self.metadata_path) as f:
                data = json.load(f)
            self.metadata = {k: FileMetadata(**v) for k, v in data.items()}

    def _save_metadata(self):
        with open(self.metadata_path, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.metadata.items()}, f, indent=2)

    def _checksum(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    # ---------- Основные операции ----------

    def put(self, filename: str, data: bytes) -> FileMetadata:
        """Сохранить файл (всегда в HOT tier)."""
        path = self.hot_path / filename
        path.write_bytes(data)

        meta = FileMetadata(
            filename=filename,
            tier=StorageTier.HOT.value,
            size=len(data),
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            checksum=self._checksum(data),
        )
        self.metadata[filename] = meta
        self._save_metadata()
        return meta

    def get(self, filename: str) -> Optional[bytes]:
        """Прочитать файл. Если он в WARM/COLD — автоматически promote в HOT."""
        if filename not in self.metadata:
            return None

        meta = self.metadata[filename]
        data = self._read_from_tier(filename, meta.tier)

        # Автоматический promote
        if meta.tier != StorageTier.HOT.value:
            self._promote_to_hot(filename, data)
            meta.tier = StorageTier.HOT.value

        meta.last_accessed = time.time()
        meta.access_count += 1
        self._save_metadata()
        return data

    def _read_from_tier(self, filename: str, tier: str) -> bytes:
        if tier == StorageTier.HOT.value:
            return (self.hot_path / filename).read_bytes()
        elif tier == StorageTier.WARM.value:
            return self.s3.get_object(Bucket=self.warm_bucket, Key=filename)["Body"].read()
        elif tier == StorageTier.COLD.value:
            return self.s3.get_object(Bucket=self.cold_bucket, Key=filename)["Body"].read()
        raise ValueError(f"Unknown tier: {tier}")

    def _promote_to_hot(self, filename: str, data: bytes):
        """Переносит файл из WARM/COLD в HOT."""
        meta = self.metadata[filename]
        # Удаляем из старого уровня
        if meta.tier == StorageTier.WARM.value:
            self.s3.delete_object(Bucket=self.warm_bucket, Key=filename)
        elif meta.tier == StorageTier.COLD.value:
            self.s3.delete_object(Bucket=self.cold_bucket, Key=filename)
        # Записываем в HOT
        (self.hot_path / filename).write_bytes(data)

    # ---------- Миграция ----------

    def migrate(self, now: Optional[float] = None) -> List[str]:
        """
        Применяет политики миграции. Возвращает список мигрированных файлов.
        now можно подменить для тестов.
        """
        now = now if now is not None else time.time()
        migrated = []

        for filename, meta in list(self.metadata.items()):
            age = now - meta.last_accessed

            if meta.tier == StorageTier.HOT.value and age > self.hot_to_warm_seconds:
                self._demote(filename, StorageTier.WARM)
                migrated.append(f"{filename}: HOT -> WARM")
                meta.tier = StorageTier.WARM.value

            elif meta.tier == StorageTier.WARM.value and age > self.warm_to_cold_seconds:
                self._demote(filename, StorageTier.COLD)
                migrated.append(f"{filename}: WARM -> COLD")
                meta.tier = StorageTier.COLD.value

        self._save_metadata()
        return migrated

    def _demote(self, filename: str, target_tier: StorageTier):
        """Переносит файл из текущего уровня на target (WARM или COLD)."""
        meta = self.metadata[filename]
        data = self._read_from_tier(filename, meta.tier)

        if target_tier == StorageTier.WARM:
            self.s3.put_object(Bucket=self.warm_bucket, Key=filename, Body=data)
        elif target_tier == StorageTier.COLD:
            self.s3.put_object(Bucket=self.cold_bucket, Key=filename, Body=data)
        else:
            raise ValueError("Нельзя демотировать в HOT")

        # Удаляем из старого уровня
        if meta.tier == StorageTier.HOT.value:
            (self.hot_path / filename).unlink(missing_ok=True)
        elif meta.tier == StorageTier.WARM.value:
            self.s3.delete_object(Bucket=self.warm_bucket, Key=filename)

    # ---------- Просмотр ----------

    def status(self) -> Dict[str, List[Dict]]:
        """Возвращает список файлов по уровням."""
        result = {"hot": [], "warm": [], "cold": []}
        for meta in self.metadata.values():
            result[meta.tier].append({
                "filename": meta.filename,
                "size": meta.size,
                "last_accessed": meta.last_accessed,
                "access_count": meta.access_count,
            })
        return result

    def print_status(self):
        """Печатает красивую таблицу."""
        status = self.status()
        print()
        print("=" * 70)
        print(f"{'HOT (' + str(len(status['hot'])) + ' files)':<70}")
        print("=" * 70)
        for f in status["hot"]:
            print(f"  {f['filename']:<30} {f['size']:>10} B  accesses={f['access_count']}")
        print()
        print(f"{'WARM (' + str(len(status['warm'])) + ' files)':<70}")
        print("-" * 70)
        for f in status["warm"]:
            print(f"  {f['filename']:<30} {f['size']:>10} B  accesses={f['access_count']}")
        print()
        print(f"{'COLD (' + str(len(status['cold'])) + ' files)':<70}")
        print("-" * 70)
        for f in status["cold"]:
            print(f"  {f['filename']:<30} {f['size']:>10} B  accesses={f['access_count']}")
        print("=" * 70)
        print()
