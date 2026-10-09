# Task 2. Benchmark: s3fs vs boto3

Сравнение производительности двух способов работы с S3-совместимым хранилищем (MinIO):
- **s3fs** — FUSE-монтирование бакета как локальной файловой системы.
- **boto3** — native S3 API через AWS SDK для Python.

## Требования

- Docker (для MinIO)
- `s3fs` (`apt-get install s3fs`)
- Python-библиотеки из `requirements.txt`

## Развёртывание MinIO

    docker compose up -d

MinIO будет доступен на `http://localhost:9000` (S3 API) и `http://localhost:9001` (Web-консоль).
Логин/пароль: `minioadmin` / `minioadmin123`.

Создание bucket:

    mc alias set local http://localhost:9000 minioadmin minioadmin123
    mc mb local/benchmark

## Монтирование s3fs

    echo 'minioadmin:minioadmin123' > ~/.passwd-s3fs
    chmod 600 ~/.passwd-s3fs
    sudo mkdir -p /mnt/s3fs
    sudo chown $USER:$USER /mnt/s3fs
    s3fs benchmark /mnt/s3fs -o passwd_file=~/.passwd-s3fs \
        -o url=http://localhost:9000 -o use_path_request_style &

## Запуск бенчмарка

    python3 -m benchmark.main --mountpoint /mnt/s3fs --iterations 50

Результаты сохраняются в `benchmark_results/`:
- `results.json` — метрики в JSON
- `throughput.png` — сравнение throughput
- `latency.png` — перцентили latency
- `iops.png` — сравнение IOPS

## Структура

    benchmark/
    ├── base.py         — базовый класс + BenchmarkResult
    ├── workloads.py    — три типа нагрузки
    ├── filesystem.py   — бенчмарки через s3fs
    ├── native_s3.py    — бенчмарки через boto3
    ├── metrics.py      — сохранение и вывод метрик
    ├── visualize.py    — графики
    └── main.py         — точка входа

## Типы нагрузок

| Workload | Параметры | Что измеряет |
|---|---|---|
| sequential_write | 50 × 1 МБ | Throughput записи |
| sequential_read | 50 × 1 МБ | Throughput чтения |
| random_io | 200 × 4 КБ | IOPS при случайном доступе |
| small_files | 200 × 4 КБ | Overhead мелких файлов |

## Результаты

Метрики на машине Codespaces (MinIO в Docker, s3fs через FUSE):

| Storage | Workload | Throughput (MB/s) | IOPS | Avg (ms) | p99 (ms) |
|---|---|---|---|---|---|
| s3fs | sequential_write | 36.27 | 36.27 | 27.573 | 65.621 |
| s3fs | sequential_read  | 201.46 | 201.46 | 4.964 | 11.141 |
| s3fs | random_io | 1.23 | 315.72 | 3.167 | 8.278 |
| s3fs | small_files | 0.58 | 147.63 | 6.774 | 58.970 |
| boto3 | sequential_write | 40.73 | 40.73 | 24.550 | 60.435 |
| boto3 | sequential_read  | 258.00 | 258.00 | 3.876 | 8.716 |
| boto3 | random_io | 1.56 | 400.08 | 2.500 | 5.241 |
| boto3 | small_files | 0.78 | 199.13 | 5.022 | 9.846 |

## Выводы

1. **boto3 (native S3) быстрее во всех сценариях.**
2. **Самая большая разница — small files** по p99 latency: 58.97 ms у s3fs против 9.85 ms у boto3 (**в 6 раз**).
3. **Sequential read:** 201 MB/s (s3fs) vs 258 MB/s (boto3), +28% у native API.
4. **Random I/O:** boto3 показывает +27% IOPS и меньший разброс.
5. **Рекомендация:**
   - Для высоконагруженных систем — native S3 API (boto3).
   - Для legacy-приложений без поддержки S3 — s3fs как адаптер.

## Ограничение: goofys

Попытка использовать `goofys` в качестве второго FUSE-решения не удалась. Версия `goofys 0.24.0` (2020) содержит устаревший AWS SDK (1.17.13, 2019) и получает `403 AccessDenied` от MinIO 2026. Форк `maxlaverse/goofys` также недоступен. Поэтому сравнение выполнено между s3fs (FUSE) и boto3 (native API) — это полностью покрывает требование «FUSE vs native S3».
