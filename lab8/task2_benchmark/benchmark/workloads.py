"""
Описание трёх типов нагрузки для бенчмарка.
"""
import os
import random


SEQUENTIAL_FILES = 50
SEQUENTIAL_SIZE = 1024 * 1024

RANDOM_BLOCK_SIZE = 4096
RANDOM_BLOCKS = 200

SMALL_FILES = 200
SMALL_SIZE = 4096


def sequential_write_workload():
    files = []
    for i in range(SEQUENTIAL_FILES):
        data = b'A' * SEQUENTIAL_SIZE
        files.append((f"seq_{i:04d}.bin", data))
    return files


def random_io_workload():
    random.seed(42)
    blocks = []
    for _ in range(RANDOM_BLOCKS):
        offset = 0
        data = os.urandom(RANDOM_BLOCK_SIZE)
        blocks.append((offset, data))
    return blocks


def small_files_workload():
    files = []
    for i in range(SMALL_FILES):
        data = os.urandom(SMALL_SIZE)
        files.append((f"small_{i:04d}.bin", data))
    return files
