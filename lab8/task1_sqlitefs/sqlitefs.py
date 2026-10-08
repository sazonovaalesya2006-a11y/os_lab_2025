#!/usr/bin/env python3
"""
SQLite FUSE файловая система.

Все данные (метаданные + содержимое по чанкам) хранятся в одном файле SQLite.
"""
import argparse
import errno
import logging
import os
import stat
import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

from database import Database, CHUNK_SIZE, S_IFDIR, S_IFREG


class SQLiteFS(Operations):
    """FUSE-операции поверх SQLite."""

    def __init__(self, db_path: str, uid: int = None, gid: int = None):
        self.db = Database(db_path)
        # uid/gid по умолчанию — текущего пользователя
        self.uid = uid if uid is not None else os.getuid()
        self.gid = gid if gid is not None else os.getgid()

    # ---------- Утилиты ----------

    def _parent(self, path: str) -> str:
        """Возвращает путь родительской директории."""
        if path == "/":
            return "/"
        parent = os.path.dirname(path.rstrip("/"))
        return parent if parent else "/"

    def _check_parent_exists(self, path: str) -> None:
        """Родительская директория должна существовать."""
        parent = self._parent(path)
        node = self.db.get_node(parent)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if not (node["mode"] & S_IFDIR):
            raise FuseOSError(errno.ENOTDIR)

    # ---------- Основные операции ----------

    def getattr(self, path, fh=None):
        """Возвращает атрибуты файла/директории в формате stat."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        return {
            "st_mode":  node["mode"],
            "st_nlink": node["nlink"],
            "st_uid":   node["uid"],
            "st_gid":   node["gid"],
            "st_size":  node["size"],
            "st_atime": node["atime"],
            "st_mtime": node["mtime"],
            "st_ctime": node["ctime"],
        }

    def readdir(self, path, fh):
        """Возвращает список имён в директории."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if not (node["mode"] & S_IFDIR):
            raise FuseOSError(errno.ENOTDIR)

        entries = [".", ".."]
        for child in self.db.list_dir(path):
            name = os.path.basename(child["path"])
            if name:
                entries.append(name)
        return entries

    def create(self, path, mode, fi=None):
        """Создаёт новый файл (вызывается при open с O_CREAT)."""
        self._check_parent_exists(path)
        if self.db.get_node(path) is not None:
            raise FuseOSError(errno.EEXIST)
        # S_IFREG | права
        self.db.create_node(path, S_IFREG | (mode & 0o777), self.uid, self.gid, size=0)
        return 0

    def open(self, path, flags):
        """Проверяем, что файл существует, и возвращаем фейковый fd."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if node["mode"] & S_IFDIR:
            raise FuseOSError(errno.EISDIR)
        return 0

    def read(self, path, size, offset, fh):
        """Читает size байт начиная с offset."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)

        if offset >= node["size"]:
            return b""

        # Какие чанки нам нужны
        start_chunk = offset // CHUNK_SIZE
        end_byte = min(offset + size, node["size"])
        end_chunk = (end_byte + CHUNK_SIZE - 1) // CHUNK_SIZE

        chunks = self.db.read_chunks(node["id"], start_chunk, end_chunk)
        result = bytearray()
        for ch in chunks:
            result.extend(ch["data"])

        # Обрезаем до нужного диапазона внутри собранного блока
        # (на случай, если offset не выровнен по границе чанка)
        inner_offset = offset - start_chunk * CHUNK_SIZE
        return bytes(result[inner_offset:inner_offset + (end_byte - offset)])

    def write(self, path, data, offset, fh):
        """Записывает data начиная с offset. Возвращает число записанных байт."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)

        file_id = node["id"]
        data_len = len(data)

        # Первый и последний чанк, которые надо обновить
        start_chunk = offset // CHUNK_SIZE
        end_offset = offset + data_len
        end_chunk = (end_offset + CHUNK_SIZE - 1) // CHUNK_SIZE

        # Достаём существующие чанки (если нужно — для частичной перезаписи)
        existing = {
            row["chunk_index"]: row["data"]
            for row in self.db.read_chunks(file_id, start_chunk, end_chunk)
        }

        pos = 0
        for idx in range(start_chunk, end_chunk):
            chunk_global_start = idx * CHUNK_SIZE
            chunk_global_end = chunk_global_start + CHUNK_SIZE

            # Часть чанка, которую затрагивает наша запись
            overlap_start = max(offset, chunk_global_start)
            overlap_end = min(end_offset, chunk_global_end)
            overlap_len = overlap_end - overlap_start
            if overlap_len <= 0:
                continue

            old = existing.get(idx, b"")
            # Приводим old к длине CHUNK_SIZE (или меньше для последнего)
            inner_start = overlap_start - chunk_global_start
            inner_end = inner_start + overlap_len

            # Расширяем old нулями, если он короче
            if len(old) < inner_end:
                old = old + b"\x00" * (inner_end - len(old))

            new_data = old[:inner_start] + data[pos:pos + overlap_len] + old[inner_end:]
            self.db.write_chunk(file_id, idx, new_data)
            pos += overlap_len

        # Обновляем размер и mtime
        new_size = max(node["size"], end_offset)
        now = time.time()
        self.db.update_node(path, size=new_size, mtime=now, ctime=now)
        return data_len

    def truncate(self, path, length, fh=None):
        """Обрезает или расширяет файл до length байт."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        file_id = node["id"]
        old_size = node["size"]

        if length < old_size:
            # Удаляем чанки целиком за пределами length
            keep_chunks = (length + CHUNK_SIZE - 1) // CHUNK_SIZE
            self.db.delete_chunks_from(file_id, keep_chunks)

            # У последнего оставшегося чанка обрезаем хвост
            if length > 0 and keep_chunks > 0:
                last_idx = keep_chunks - 1
                last_start = last_idx * CHUNK_SIZE
                cut_in_chunk = length - last_start
                rows = self.db.read_chunks(file_id, last_idx, last_idx + 1)
                if rows:
                    self.db.write_chunk(file_id, last_idx, rows[0]["data"][:cut_in_chunk])
        else:
            # Расширяем нулями
            last_chunk = (length + CHUNK_SIZE - 1) // CHUNK_SIZE - 1
            if last_chunk >= 0:
                rows = self.db.read_chunks(file_id, last_chunk, last_chunk + 1)
                if rows:
                    cur = rows[0]["data"]
                    need = length - last_chunk * CHUNK_SIZE
                    if len(cur) < need:
                        self.db.write_chunk(file_id, last_chunk, cur + b"\x00" * (need - len(cur)))

        now = time.time()
        self.db.update_node(path, size=length, mtime=now, ctime=now)

    def unlink(self, path):
        """Удаляет файл."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if node["mode"] & S_IFDIR:
            raise FuseOSError(errno.EISDIR)
        self.db.delete_node(path)

    def mkdir(self, path, mode):
        """Создаёт директорию."""
        self._check_parent_exists(path)
        if self.db.get_node(path) is not None:
            raise FuseOSError(errno.EEXIST)
        self.db.create_node(path, S_IFDIR | (mode & 0o777), self.uid, self.gid)

    def rmdir(self, path):
        """Удаляет пустую директорию."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        if not (node["mode"] & S_IFDIR):
            raise FuseOSError(errno.ENOTDIR)
        if path == "/":
            raise FuseOSError(errno.EBUSY)
        # Проверяем, что директория пуста
        if self.db.list_dir(path):
            raise FuseOSError(errno.ENOTEMPTY)
        self.db.delete_node(path)

    def rename(self, old, new):
        """Переименовывает файл/директорию."""
        if self.db.get_node(old) is None:
            raise FuseOSError(errno.ENOENT)
        self._check_parent_exists(new)
        if self.db.get_node(new) is not None:
            raise FuseOSError(errno.EEXIST)
        self.db.rename(old, new)
        now = time.time()
        self.db.update_node(new, ctime=now)

    def chmod(self, path, mode):
        """Изменяет права доступа."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        # Сохраняем флаг типа файла (S_IFDIR / S_IFREG) и меняем права
        new_mode = (node["mode"] & 0o170000) | (mode & 0o7777)
        self.db.update_node(path, mode=new_mode, ctime=time.time())

    def chown(self, path, uid, gid):
        """Изменяет владельца и группу."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        self.db.update_node(path, uid=uid, gid=gid, ctime=time.time())

    def utimens(self, path, times=None):
        """Обновляет atime и mtime."""
        node = self.db.get_node(path)
        if node is None:
            raise FuseOSError(errno.ENOENT)
        now = time.time()
        atime, mtime = times if times else (now, now)
        self.db.update_node(path, atime=atime, mtime=mtime, ctime=now)


    def statfs(self, path):
        """Псевдо-статистика ФС (не обязательна, но некоторые утилиты её требуют)."""
        return {
            "f_bsize":   CHUNK_SIZE,
            "f_frsize":  CHUNK_SIZE,
            "f_blocks":  0,
            "f_bfree":   0,
            "f_bavail":  0,
            "f_files":   0,
            "f_ffree":   0,
            "f_favail":  0,
            "f_namemax": 255,
        }


def main():
    parser = argparse.ArgumentParser(description="SQLite FUSE filesystem")
    parser.add_argument("mountpoint", help="Точка монтирования")
    parser.add_argument("--database", required=True, help="Путь к SQLite БД")
    parser.add_argument("--foreground", "-f", action="store_true",
                        help="Не уходить в фон (для отладки)")
    parser.add_argument("--debug", action="store_true", help="Debug-логи")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    fs = SQLiteFS(args.database)
    FUSE(
        fs,
        args.mountpoint,
        foreground=args.foreground,
        nothreads=False,  # разрешаем многопоточность
        ro=False,
    )


if __name__ == "__main__":
    main()
