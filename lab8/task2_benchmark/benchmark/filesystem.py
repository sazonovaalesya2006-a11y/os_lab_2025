"""
Бенчмарки для FUSE (s3fs).
"""
import os
import random
from .base import BenchmarkBase
from . import workloads


class FilesystemSequentialWrite(BenchmarkBase):
    def __init__(self, mountpoint: str):
        super().__init__(storage="s3fs", workload="sequential_write")
        self.mountpoint = mountpoint
        self.files = []

    def setup(self):
        self.files = workloads.sequential_write_workload()
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, data = self.files[self._idx]
        self._idx += 1
        path = os.path.join(self.mountpoint, name)
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    def cleanup(self):
        for name, _ in self.files:
            try:
                os.remove(os.path.join(self.mountpoint, name))
            except FileNotFoundError:
                pass


class FilesystemSequentialRead(BenchmarkBase):
    def __init__(self, mountpoint: str):
        super().__init__(storage="s3fs", workload="sequential_read")
        self.mountpoint = mountpoint
        self.files = []

    def setup(self):
        self.files = workloads.sequential_write_workload()
        for name, data in self.files:
            with open(os.path.join(self.mountpoint, name), "wb") as f:
                f.write(data)
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, _ = self.files[self._idx]
        self._idx += 1
        with open(os.path.join(self.mountpoint, name), "rb") as f:
            data = f.read()
        return len(data)

    def cleanup(self):
        for name, _ in self.files:
            try:
                os.remove(os.path.join(self.mountpoint, name))
            except FileNotFoundError:
                pass


class FilesystemRandomIO(BenchmarkBase):
    def __init__(self, mountpoint: str):
        super().__init__(storage="s3fs", workload="random_io")
        self.mountpoint = mountpoint
        self.filename = "random_io.bin"
        self.file_size = workloads.RANDOM_BLOCK_SIZE * workloads.RANDOM_BLOCKS

    def setup(self):
        path = os.path.join(self.mountpoint, self.filename)
        with open(path, "wb") as f:
            f.write(b"B" * self.file_size)
        self._offsets = [random.randrange(0, self.file_size, workloads.RANDOM_BLOCK_SIZE)
                         for _ in range(workloads.RANDOM_BLOCKS)]
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self._offsets):
            return 0
        offset = self._offsets[self._idx]
        self._idx += 1
        path = os.path.join(self.mountpoint, self.filename)
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(workloads.RANDOM_BLOCK_SIZE)
        return len(data)

    def cleanup(self):
        try:
            os.remove(os.path.join(self.mountpoint, self.filename))
        except FileNotFoundError:
            pass


class FilesystemSmallFiles(BenchmarkBase):
    def __init__(self, mountpoint: str):
        super().__init__(storage="s3fs", workload="small_files")
        self.mountpoint = mountpoint
        self.files = []

    def setup(self):
        self.files = workloads.small_files_workload()
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= len(self.files):
            return 0
        name, data = self.files[self._idx]
        self._idx += 1
        with open(os.path.join(self.mountpoint, name), "wb") as f:
            f.write(data)
        return len(data)

    def cleanup(self):
        for name, _ in self.files:
            try:
                os.remove(os.path.join(self.mountpoint, name))
            except FileNotFoundError:
                pass

class FilesystemMetadataOps(BenchmarkBase):
    """stat + create + delete одного файла (200 раз)."""

    def __init__(self, mountpoint: str):
        super().__init__(storage="s3fs", workload="metadata_ops")
        self.mountpoint = mountpoint
        self.fixed_file = "metadata_fixed.txt"

    def setup(self):
        # Создаём файл, который будем stat-ить
        with open(os.path.join(self.mountpoint, self.fixed_file), "wb") as f:
            f.write(b"x")
        self._idx = 0

    def run_iteration(self) -> int:
        if self._idx >= workloads.METADATA_OPS:
            return 0
        self._idx += 1
        # 1 stat
        os.stat(os.path.join(self.mountpoint, self.fixed_file))
        # 2 create
        tmp_name = f"meta_tmp_{self._idx}.txt"
        tmp_path = os.path.join(self.mountpoint, tmp_name)
        with open(tmp_path, "wb") as f:
            f.write(b"x")
        # 3 delete
        os.remove(tmp_path)
        return 3  # 3 операции метаданных

    def cleanup(self):
        try:
            os.remove(os.path.join(self.mountpoint, self.fixed_file))
        except FileNotFoundError:
            pass
