# Task 1. SQLite FUSE filesystem

FUSE-файловая система на Python: все данные (метаданные + содержимое) хранятся в SQLite.

## Возможности

- Создание/удаление файлов и директорий: create, unlink, mkdir, rmdir
- Чтение/запись: read, write
- Метаданные: getattr, chmod, chown, utimens
- Переименование: rename
- Обрезка: truncate
- Чанковое хранение содержимого (по 4 КБ)
- Персистентность между перезапусками

## Установка

    sudo apt-get install -y fuse libfuse2
    pip install -r requirements.txt

## Запуск

    mkdir -p /tmp/sqlitefs_mnt
    python3 sqlitefs.py /tmp/sqlitefs_mnt --database /tmp/test_fs.db --foreground

Во втором терминале:

    echo 'Hello, FUSE!' > /tmp/sqlitefs_mnt/test.txt
    cat /tmp/sqlitefs_mnt/test.txt
    ls -la /tmp/sqlitefs_mnt/

## Размонтирование

    fusermount -u /tmp/sqlitefs_mnt

## Тесты

    coverage run -m unittest test_sqlitefs
    coverage report -m sqlitefs.py database.py

Покрытие: 89% (34 теста).

## Структура

- database.py — обёртка над SQLite
- sqlitefs.py — реализация FUSE-операций
- test_sqlitefs.py — unit-тесты
