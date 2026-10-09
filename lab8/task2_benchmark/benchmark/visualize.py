import os
from collections import defaultdict
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .base import BenchmarkResult


def _group_by_workload(results):
    grouped = defaultdict(dict)
    for r in results:
        grouped[r.workload][r.storage] = r
    return grouped


def plot_throughput_comparison(results, output_path):
    grouped = _group_by_workload(results)
    workloads = sorted(grouped.keys())
    storages = sorted({r.storage for r in results})
    x = np.arange(len(workloads))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, storage in enumerate(storages):
        values = [grouped[w].get(storage).throughput_mbps if storage in grouped[w] else 0
                  for w in workloads]
        bars = ax.bar(x + i * width - width / 2, values, width, label=storage)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("Workload")
    ax.set_ylabel("Throughput (MB/s)")
    ax.set_title("Throughput: s3fs (FUSE) vs boto3 (native S3)")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads, rotation=15)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_latency_percentiles(results, output_path):
    grouped = _group_by_workload(results)
    workloads = sorted(grouped.keys())
    storages = sorted({r.storage for r in results})
    metrics = ["latency_avg_ms", "latency_p95_ms", "latency_p99_ms"]
    labels = ["avg", "p95", "p99"]

    fig, axes = plt.subplots(1, len(workloads), figsize=(5 * len(workloads), 5), sharey=True)
    if len(workloads) == 1:
        axes = [axes]
    x = np.arange(len(storages))
    width = 0.25

    for ax, w in zip(axes, workloads):
        for i, (metric, label) in enumerate(zip(metrics, labels)):
            values = []
            for storage in storages:
                r = grouped[w].get(storage)
                values.append(getattr(r, metric) if r else 0)
            ax.bar(x + i * width - width, values, width, label=label)
        ax.set_title(w)
        ax.set_xticks(x)
        ax.set_xticklabels(storages, rotation=15)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("Latency (ms)")
    fig.suptitle("Latency percentiles: s3fs (FUSE) vs boto3 (native S3)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_iops_comparison(results, output_path):
    grouped = _group_by_workload(results)
    workloads = sorted(grouped.keys())
    storages = sorted({r.storage for r in results})
    x = np.arange(len(workloads))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, storage in enumerate(storages):
        values = [grouped[w].get(storage).iops if storage in grouped[w] else 0
                  for w in workloads]
        bars = ax.bar(x + i * width - width / 2, values, width, label=storage)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("Workload")
    ax.set_ylabel("IOPS")
    ax.set_title("IOPS: s3fs (FUSE) vs boto3 (native S3)")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads, rotation=15)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {output_path}")


def make_all_plots(results, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    plot_throughput_comparison(results, os.path.join(output_dir, "throughput.png"))
    plot_latency_percentiles(results, os.path.join(output_dir, "latency.png"))
    plot_iops_comparison(results, os.path.join(output_dir, "iops.png"))
