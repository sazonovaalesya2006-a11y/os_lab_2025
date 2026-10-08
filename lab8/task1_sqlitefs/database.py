"""
Модуль работы с SQLite для FUSE-файловой системы.

Хранит метаданные файлов (таблица files) и содержимое (таблица file_data).
Файлы хранятся по чанкам (по умолчанию 4096 байт).
"""
import sqlite3
import threading
import time
from typing import Optional, List, Dict, Any

# Размер чанка в байтах (4 КБ)
CHUNK_SIZE = 4096

# Флаги типов файлов (для режима, как в stat.h)
S_IFDIR = 0o040000
S_IFREG = 0o100000


class Database:
    """Потокобезопасная обёртка над SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # SQLite не очень любит многопоточность — защищаемся мьютексом
        self.lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Новое соединение с включёнными foreign keys."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # доступ к колонкам по имени
        return conn

    def _init_db(self) -> None:
        """Создаёт таблицы, если их нет, и корневую директорию '/'."""
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            # Метаданные файлов
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    path     TEXT UNIQUE NOT NULL,
                    mode     INTEGER NOT NULL,
                    uid      INTEGER NOT NULL,
                    gid      INTEGER NOT NULL,
                    size     INTEGER DEFAULT 0,
                    atime    REAL NOT NULL,
                    mtime    REAL NOT NULL,
                    ctime    REAL NOT NULL,
                    nlink    INTEGER DEFAULT 1
                )
            """)
            # Содержимое файлов по чанкам
            cur.execute("""
                CREATE TABLE IF NOT EXISTS file_data (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id     INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    data        BLOB,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                    UNIQUE(file_id, chunk_index)
                )
            """)
            # Индексы
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_file_data_file_id ON file_data(file_id)")

            # Создаём корневую директорию, если её нет
            now = time.time()
            cur.execute("SELECT id FROM files WHERE path = '/'")
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO files (path, mode, uid, gid, size, atime, mtime, ctime, nlink) "
                    "VALUES (?, ?, ?, ?, 0, ?, ?, ?, 2)",
                    ("/", S_IFDIR | 0o755, 0, 0, now, now, now),
                )
            conn.commit()
            conn.close()

    # ---------- Работа с метаданными ----------

    def create_node(self, path: str, mode: int, uid: int, gid: int, size: int = 0) -> int:
        """Создаёт запись файла/директории. Возвращает id."""
        now = time.time()
        nlink = 2 if (mode & S_IFDIR) else 1
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO files (path, mode, uid, gid, size, atime, mtime, ctime, nlink) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (path, mode, uid, gid, size, now, now, now, nlink),
            )
            file_id = cur.lastrowid
            conn.commit()
            conn.close()
        return file_id

    def get_node(self, path: str) -> Optional[Dict[str, Any]]:
        """Возвращает запись по пути или None."""
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT * FROM files WHERE path = ?", (path,))
            row = cur.fetchone()
            conn.close()
        return dict(row) if row else None

    def update_node(self, path: str, **fields) -> None:
        """Обновляет произвольные поля записи (size, atime, mtime, ctime, mode, uid, gid, nlink)."""
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [path]
        with self.lock:
            conn = self._connect()
            conn.execute(f"UPDATE files SET {cols} WHERE path = ?", vals)
            conn.commit()
            conn.close()

    def delete_node(self, path: str) -> None:
        """Удаляет запись (file_data удалится каскадно)."""
        with self.lock:
            conn = self._connect()
            conn.execute("DELETE FROM files WHERE path = ?", (path,))
            conn.commit()
            conn.close()

    def list_dir(self, parent_path: str) -> List[Dict[str, Any]]:
        """Возвращает прямых потомков директории."""
        if parent_path == "/":
            prefix = "/"
        else:
            prefix = parent_path + "/"
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            # LIKE для быстрого поиска прямых детей. Отсекаем более глубокие
            cur.execute(
                "SELECT * FROM files WHERE path LIKE ? AND path != ?",
                (prefix + "%", parent_path),
            )
            rows = cur.fetchall()
            conn.close()
        # Фильтруем только прямых детей (в пути после prefix нет '/')
        result = []
        for row in rows:
            rel = row["path"][len(prefix):]
            if "/" not in rel and rel != "":
                result.append(dict(row))
        return result

    def rename(self, old_path: str, new_path: str) -> None:
        """Переименовывает файл/директорию (включая всех потомков)."""
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            # Меняем сам узел
            cur.execute("UPDATE files SET path = ? WHERE path = ?", (new_path, old_path))
            # И всех его потомков (если это директория)
            old_prefix = old_path + "/"
            new_prefix = new_path + "/"
            cur.execute(
                "UPDATE files SET path = ? || SUBSTR(path, ?) WHERE path LIKE ?",
                (new_prefix, len(old_prefix) + 1, old_prefix + "%"),
            )
            conn.commit()
            conn.close()

    # ---------- Работа с содержимым (чанки) ----------

    def write_chunk(self, file_id: int, chunk_index: int, data: bytes) -> None:
        """Записывает/перезаписывает один чанк."""
        with self.lock:
            conn = self._connect()
            conn.execute(
                "INSERT OR REPLACE INTO file_data (file_id, chunk_index, data) "
                "VALUES (?, ?, ?)",
                (file_id, chunk_index, data),
            )
            conn.commit()
            conn.close()

    def read_chunks(self, file_id: int, start_chunk: int, end_chunk: int) -> List[sqlite3.Row]:
        """Возвращает чанки с индексами [start_chunk, end_chunk)."""
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT chunk_index, data FROM file_data "
                "WHERE file_id = ? AND chunk_index >= ? AND chunk_index < ? "
                "ORDER BY chunk_index",
                (file_id, start_chunk, end_chunk),
            )
            rows = cur.fetchall()
            conn.close()
        return rows

    def delete_chunks_from(self, file_id: int, from_chunk: int) -> None:
        """Удаляет все чанки, начиная с указанного индекса (для truncate)."""
        with self.lock:
            conn = self._connect()
            conn.execute(
                "DELETE FROM file_data WHERE file_id = ? AND chunk_index >= ?",
                (file_id, from_chunk),
            )
            conn.commit()
            conn.close()

    def get_last_chunk_index(self, file_id: int) -> int:
        """Возвращает индекс последнего существующего чанка (-1 если чанков нет)."""
        with self.lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT MAX(chunk_index) as m FROM file_data WHERE file_id = ?", (file_id,)
            )
            row = cur.fetchone()
            conn.close()
        return row["m"] if row["m"] is not None else -1
