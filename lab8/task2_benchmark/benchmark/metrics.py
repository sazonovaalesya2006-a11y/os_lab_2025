import json
from typing import List
from .base import BenchmarkResult


def save_results(results: List[BenchmarkResult], path: str) -> None:
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)


def load_results(path: str) -> List[BenchmarkResult]:
    with open(path) as f:
        data = json.load(f)
    return [BenchmarkResult(**item) for item in data]


def print_summary(results: List[BenchmarkResult]) -> None:
    print()
    print(f"{'Storage':<10} {'Workload':<20} {'Throughput':>12} {'IOPS':>10} "
          f"{'Avg(ms)':>10} {'p95(ms)':>10} {'p99(ms)':>10} {'Errors':>8}")
    print("-" * 100)
    for r in results:
        print(f"{r.storage:<10} {r.workload:<20} {r.throughput_mbps:>12.2f} "
              f"{r.iops:>10.2f} {r.latency_avg_ms:>10.3f} {r.latency_p95_ms:>10.3f} "
              f"{r.latency_p99_ms:>10.3f} {r.errors:>8}")
    print()
