"""
Автоматический сценарий демонстрации гибридного хранилища.

Прогоняет полный цикл:
1. Создаёт файлы (в HOT).
2. Эмулирует "прошло 10 дней" → migrate → HOT → WARM.
3. Эмулирует "прошло 40 дней" → migrate → WARM → COLD.
4. Обращается к файлу в COLD → авто-promote в HOT.
5. Печатает финальный status.
"""
import time
from app.hybrid_storage import HybridStorageManager


def separator(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    separator("Шаг 1. Инициализация менеджера")
    mgr = HybridStorageManager()
    print("Bucket'ы hybrid-warm и hybrid-cold готовы, hot_storage/ создан.")

    # Чистим метаданные для чистого прогона
    mgr.metadata = {}
    mgr._save_metadata()

    separator("Шаг 2. Кладём три файла в HOT")
    mgr.put("video_1.mp4", b"video content 1" * 100)
    mgr.put("video_2.mp4", b"video content 2" * 200)
    mgr.put("video_3.mp4", b"video content 3" * 300)
    print("Положено 3 файла.")
    mgr.print_status()

    separator("Шаг 3. Эмулируем 'прошло 10 дней' → migrate (HOT → WARM)")
    now_plus_10 = time.time() + 10 * 86400
    migrated = mgr.migrate(now=now_plus_10)
    for m in migrated:
        print(f"  {m}")
    mgr.print_status()

    separator("Шаг 4. Эмулируем 'прошло 40 дней' → migrate (WARM → COLD)")
    now_plus_40 = time.time() + 40 * 86400
    migrated = mgr.migrate(now=now_plus_40)
    for m in migrated:
        print(f"  {m}")
    mgr.print_status()

    separator("Шаг 5. Обращаемся к video_2.mp4 (в COLD) → авто-promote в HOT")
    data = mgr.get("video_2.mp4")
    print(f"Прочитано {len(data)} байт из video_2.mp4")
    print(f"Текущий tier: {mgr.metadata['video_2.mp4'].tier}")
    mgr.print_status()

    separator("Сценарий завершён")


if __name__ == "__main__":
    main()
