"""
Базовый интерфейс для всех бенчмарков.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class BenchmarkResult:
    """Результат одного бенчмарка."""
    name: str
    storage: str
    workload: str
    iterations: int
    total_bytes: int
    throughput_mbps: float
    iops: float
    latency_avg_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_min_ms: float
    latency_max_ms: float
    errors: int

    def to_dict(self):
        return asdict(self)


class BenchmarkBase(ABC):
    """Абстрактный базовый класс для бенчмарков."""

    def __init__(self, storage: str, workload: str, **params):
        self.storage = storage
        self.workload = workload
        self.params = params
        self.name = f"{storage}_{workload}"
        self.latencies: List[float] = []
        self.errors = 0

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def run_iteration(self) -> int:
        pass

    @abstractmethod
    def cleanup(self):
        pass

    def run(self, iterations: int) -> BenchmarkResult:
        print(f"[{self.name}] setup...")
        self.setup()

        total_bytes = 0
        self.latencies = []
        self.errors = 0

        print(f"[{self.name}] running {iterations} iterations...")
        for i in range(iterations):
            start = time.perf_counter()
            try:
                nbytes = self.run_iteration()
                total_bytes += nbytes
            except Exception as e:
                self.errors += 1
                print(f"  iteration {i}: ERROR {e}")
                nbytes = 0
            elapsed = (time.perf_counter() - start) * 1000.0
            self.latencies.append(elapsed)

        print(f"[{self.name}] cleanup...")
        self.cleanup()

        return self._calculate_results(iterations, total_bytes)

    def _calculate_results(self, iterations: int, total_bytes: int) -> BenchmarkResult:
        if not self.latencies:
            return BenchmarkResult(
                name=self.name, storage=self.storage, workload=self.workload,
                iterations=0, total_bytes=0, throughput_mbps=0.0, iops=0.0,
                latency_avg_ms=0.0, latency_p95_ms=0.0, latency_p99_ms=0.0,
                latency_min_ms=0.0, latency_max_ms=0.0, errors=self.errors,
            )

        lat = sorted(self.latencies)
        n = len(lat)
        total_time_s = sum(lat) / 1000.0

        throughput = (total_bytes / (1024 * 1024)) / total_time_s if total_time_s > 0 else 0.0
        iops = n / total_time_s if total_time_s > 0 else 0.0

        return BenchmarkResult(
            name=self.name,
            storage=self.storage,
            workload=self.workload,
            iterations=n,
            total_bytes=total_bytes,
            throughput_mbps=round(throughput, 2),
            iops=round(iops, 2),
            latency_avg_ms=round(sum(lat) / n, 3),
            latency_p95_ms=round(lat[int(n * 0.95)] if n > 1 else lat[0], 3),
            latency_p99_ms=round(lat[int(n * 0.99)] if n > 1 else lat[0], 3),
            latency_min_ms=round(lat[0], 3),
            latency_max_ms=round(lat[-1], 3),
            errors=self.errors,
        )
