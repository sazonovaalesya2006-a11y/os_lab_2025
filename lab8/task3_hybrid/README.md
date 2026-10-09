# Task 3. Гибридное хранилище (HOT + WARM + COLD)

Демонстрация трёхуровневого гибридного хранилища для компании TechData Solutions.

## Архитектура

- **HOT** — локальный диск (`hot_storage/`), активные данные.
- **WARM** — MinIO bucket `hybrid-warm`, недавние данные.
- **COLD** — MinIO bucket `hybrid-cold`, архивы.

Подробнее см. [ARCHITECTURE.md](ARCHITECTURE.md).

## Требования

- Docker (для MinIO)
- Python 3.10+
- `pip install -r app/requirements.txt`

## Установка

    pip install -r app/requirements.txt

## Запуск MinIO

    docker compose up -d minio

Проверка:

    curl -sf http://localhost:9000/minio/health/live && echo "MinIO OK"

## Интерактивное демо

    python3 -m app.demo

Команды:
- `put <filename> <content>` — положить файл в HOT
- `get <filename>` — прочитать (авто-promote из WARM/COLD)
- `status` — показать все файлы по уровням
- `migrate` — применить политики миграции
- `simulate_days <N>` — сдвинуть время на N дней
- `exit` — выход

## Автоматический сценарий

    python3 -m app.demo_scenario

Прогоняет полный цикл: создание файлов -> миграция HOT->WARM -> WARM->COLD -> promote.

## Docker (полная инфраструктура)

    docker compose up -d

Запускает MinIO + s3fs-контейнер + Python-контейнер.

## Структура

    task3_hybrid/
    ├── docker-compose.yml          # MinIO + s3fs + app
    ├── Dockerfile.s3fs             # образ для s3fs
    ├── scripts/
    │   └── s3fs-entrypoint.sh      # монтирование S3 при старте
    ├── app/
    │   ├── hybrid_storage.py       # менеджер трёхуровневого хранилища
    │   ├── demo.py                 # интерактивное демо
    │   ├── demo_scenario.py        # автоматический сценарий
    │   └── requirements.txt
    ├── ARCHITECTURE.md             # описание архитектуры + TCO + план
    └── README.md

## Политики миграции

| Переход | Триггер |
|---|---|
| HOT -> WARM | не читали 7 дней |
| WARM -> COLD | не читали 30 дней |
| COLD -> HOT | автоматически при чтении |
