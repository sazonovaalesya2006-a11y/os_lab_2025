"""
Бенчмарки для native S3 API (boto3).
"""
import random
import boto3
from botocore.client import Config

from .base import BenchmarkBase
from . import workloads


def make_s3_client(endpoint: str = "http://localhost:9000",
                   access_key: str = "minioadmin",
                   secret_key: str = "minioadmin123"):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


class S3SequentialWrite(BenchmarkBase):
    def __init__(self, bucket="benchmark", endpoint="http://localhost:9000"):
        super().__init__(storage="boto3", workload="sequential_write")
        self.bucket = bucket
        self.s3 = make_s3_client(endpoint)
        self.files = []

    def setup(self):
        self.files = workloads.sequential_write_workload()
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, data = self.files[self._idx]
        self._idx += 1
        self.s3.put_object(Bucket=self.bucket, Key=f"seq/{name}", Body=data)
        return len(data)

    def cleanup(self):
        for name, _ in self.files:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=f"seq/{name}")
            except Exception:
                pass


class S3SequentialRead(BenchmarkBase):
    def __init__(self, bucket="benchmark", endpoint="http://localhost:9000"):
        super().__init__(storage="boto3", workload="sequential_read")
        self.bucket = bucket
        self.s3 = make_s3_client(endpoint)
        self.files = []

    def setup(self):
        self.files = workloads.sequential_write_workload()
        for name, data in self.files:
            self.s3.put_object(Bucket=self.bucket, Key=f"seq/{name}", Body=data)
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, _ = self.files[self._idx]
        self._idx += 1
        resp = self.s3.get_object(Bucket=self.bucket, Key=f"seq/{name}")
        return len(resp["Body"].read())

    def cleanup(self):
        for name, _ in self.files:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=f"seq/{name}")
            except Exception:
                pass


class S3RandomIO(BenchmarkBase):
    def __init__(self, bucket="benchmark", endpoint="http://localhost:9000"):
        super().__init__(storage="boto3", workload="random_io")
        self.bucket = bucket
        self.s3 = make_s3_client(endpoint)
        self.key = "random_io.bin"
        self.file_size = workloads.RANDOM_BLOCK_SIZE * workloads.RANDOM_BLOCKS

    def setup(self):
        self.s3.put_object(Bucket=self.bucket, Key=self.key, Body=b"B" * self.file_size)
        self._offsets = [random.randrange(0, self.file_size, workloads.RANDOM_BLOCK_SIZE)
                         for _ in range(workloads.RANDOM_BLOCKS)]
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self._offsets):
            return 0
        offset = self._offsets[self._idx]
        self._idx += 1
        resp = self.s3.get_object(
            Bucket=self.bucket, Key=self.key,
            Range=f"bytes={offset}-{offset + workloads.RANDOM_BLOCK_SIZE - 1}",
        )
        return len(resp["Body"].read())

    def cleanup(self):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=self.key)
        except Exception:
            pass


class S3SmallFiles(BenchmarkBase):
    def __init__(self, bucket="benchmark", endpoint="http://localhost:9000"):
        super().__init__(storage="boto3", workload="small_files")
        self.bucket = bucket
        self.s3 = make_s3_client(endpoint)
        self.files = []

    def setup(self):
        self.files = workloads.small_files_workload()
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, data = self.files[self._idx]
        self._idx += 1
        self.s3.put_object(Bucket=self.bucket, Key=f"small/{name}", Body=data)
        return len(data)

    def cleanup(self):
        for name, _ in self.files:
            try:
                self.s3.delete_object(Bucket=self.bucket, Key=f"small/{name}")
            except Exception:
                pass
