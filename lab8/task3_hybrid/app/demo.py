"""
Интерактивное демо гибридного хранилища.

Команды:
  put <filename> <content>   — положить файл в HOT
  get <filename>             — прочитать файл (авто-promote если WARM/COLD)
  status                     — показать все файлы по уровням
  migrate                    — применить политики миграции
  help                       — список команд
  exit                       — выход
"""
import sys
import time
from .hybrid_storage import HybridStorageManager


def print_help():
    print("""
Команды:
  put <filename> <content>   — положить файл в HOT
  get <filename>             — прочитать файл (авто-promote)
  status                     — показать все файлы по уровням
  migrate                    — применить политики миграции
  simulate_days <N>          — сдвинуть время на N дней (для теста миграции)
  help                       — эта справка
  exit                       — выход
""")


def main():
    print("=== Hybrid Storage Demo ===")
    print("Инициализация менеджера (создание bucket'ов в MinIO)...")
    mgr = HybridStorageManager()
    print("Готово. Введите 'help' для списка команд.")

    time_offset_days = 0  # искусственный сдвиг времени для теста

    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "exit" or cmd == "quit":
            break

        elif cmd == "help":
            print_help()

        elif cmd == "put":
            if len(parts) < 3:
                print("Использование: put <filename> <content>")
                continue
            filename, content = parts[1], parts[2]
            meta = mgr.put(filename, content.encode())
            print(f"OK: {filename} ({meta.size} B) → HOT")

        elif cmd == "get":
            if len(parts) < 2:
                print("Использование: get <filename>")
                continue
            filename = parts[1]
            data = mgr.get(filename)
            if data is None:
                print(f"Файл {filename} не найден")
            else:
                meta = mgr.metadata[filename]
                print(f"Data: {data.decode(errors='replace')}")
                print(f"Tier: {meta.tier}, accesses: {meta.access_count}")

        elif cmd == "status":
            mgr.print_status()

        elif cmd == "migrate":
            # применяем сдвиг времени
            now = time.time() + time_offset_days * 86400
            migrated = mgr.migrate(now=now)
            if migrated:
                print(f"Мигрировано {len(migrated)} файлов:")
                for m in migrated:
                    print(f"  {m}")
            else:
                print("Нечего мигрировать")

        elif cmd == "simulate_days":
            if len(parts) < 2:
                print("Использование: simulate_days <N>")
                continue
            try:
                time_offset_days = float(parts[1])
                print(f"Сдвиг времени: +{time_offset_days} дней. Теперь 'migrate' будет считать, что прошло столько времени.")
            except ValueError:
                print("N должно быть числом")

        else:
            print(f"Неизвестная команда: {cmd}")


if __name__ == "__main__":
    main()
