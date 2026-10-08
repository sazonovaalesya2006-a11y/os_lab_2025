"""
Unit-тесты для SQLiteFS.

Тестируем логику напрямую через класс SQLiteFS (без монтирования FUSE).
Это быстро и стабильно: не нужен /dev/fuse, не нужны root-права.
"""
import errno
import os
import stat
import tempfile
import unittest

from fuse import FuseOSError

from database import S_IFDIR, S_IFREG, CHUNK_SIZE
from sqlitefs import SQLiteFS


class TestSQLiteFS(unittest.TestCase):

    def setUp(self):
        """Перед каждым тестом — свежая временная БД и экземпляр ФС."""
        self.tmp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.tmp_db.close()
        self.fs = SQLiteFS(self.tmp_db.name, uid=os.getuid(), gid=os.getgid())

    def tearDown(self):
        try:
            os.unlink(self.tmp_db.name)
        except FileNotFoundError:
            pass

    # ---------- getattr ----------

    def test_root_exists(self):
        attr = self.fs.getattr('/')
        self.assertTrue(stat.S_ISDIR(attr['st_mode']))

    def test_getattr_nonexistent(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.getattr('/no_such_file')
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    # ---------- create / write / read ----------

    def test_create_and_getattr(self):
        self.fs.create('/test.txt', 0o644)
        attr = self.fs.getattr('/test.txt')
        self.assertTrue(stat.S_ISREG(attr['st_mode']))
        self.assertEqual(attr['st_size'], 0)
        self.assertEqual(attr['st_uid'], os.getuid())

    def test_create_duplicate_raises(self):
        self.fs.create('/test.txt', 0o644)
        with self.assertRaises(FuseOSError) as cm:
            self.fs.create('/test.txt', 0o644)
        self.assertEqual(cm.exception.errno, errno.EEXIST)

    def test_create_in_nonexistent_dir(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.create('/nodir/file.txt', 0o644)
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    def test_write_and_read(self):
        self.fs.create('/test.txt', 0o644)
        written = self.fs.write('/test.txt', b'Hello, FUSE!', 0, None)
        self.assertEqual(written, 12)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'Hello, FUSE!')

    def test_write_at_offset(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'Hello', 0, None)
        self.fs.write('/test.txt', b'World', 5, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'HelloWorld')

    def test_write_overwrites(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'AAAAAAAA', 0, None)
        self.fs.write('/test.txt', b'BB', 2, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'AABBAAAA')

    def test_read_beyond_eof(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'abc', 0, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 100, None), b'')

    def test_read_partial(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'Hello, World!', 0, None)
        self.assertEqual(self.fs.read('/test.txt', 5, 0, None), b'Hello')
        self.assertEqual(self.fs.read('/test.txt', 5, 7, None), b'World')

    def test_read_large_file_across_chunks(self):
        """Файл больше одного чанка — проверяем чанковое хранение."""
        self.fs.create('/big.bin', 0o644)
        data = b'A' * (CHUNK_SIZE * 3 + 100)
        self.fs.write('/big.bin', data, 0, None)
        self.assertEqual(self.fs.read('/big.bin', len(data), 0, None), data)
        # Чтение, пересекающее границу чанка
        self.assertEqual(
            self.fs.read('/big.bin', 200, CHUNK_SIZE - 50, None),
            data[CHUNK_SIZE - 50:CHUNK_SIZE - 50 + 200],
        )

    # ---------- truncate ----------

    def test_truncate_shrink(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'Hello, World!', 0, None)
        self.fs.truncate('/test.txt', 5, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'Hello')
        self.assertEqual(self.fs.getattr('/test.txt')['st_size'], 5)

    def test_truncate_grow(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'abc', 0, None)
        self.fs.truncate('/test.txt', 6, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'abc\x00\x00\x00')

    def test_truncate_to_zero(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.write('/test.txt', b'Hello', 0, None)
        self.fs.truncate('/test.txt', 0, None)
        self.assertEqual(self.fs.read('/test.txt', 100, 0, None), b'')
        self.assertEqual(self.fs.getattr('/test.txt')['st_size'], 0)

    # ---------- unlink ----------

    def test_unlink(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.unlink('/test.txt')
        with self.assertRaises(FuseOSError):
            self.fs.getattr('/test.txt')

    def test_unlink_nonexistent(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.unlink('/no_such.txt')
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    def test_unlink_directory_raises(self):
        self.fs.mkdir('/mydir', 0o755)
        with self.assertRaises(FuseOSError) as cm:
            self.fs.unlink('/mydir')
        self.assertEqual(cm.exception.errno, errno.EISDIR)

    # ---------- mkdir / rmdir / readdir ----------

    def test_mkdir_and_readdir(self):
        self.fs.mkdir('/mydir', 0o755)
        attr = self.fs.getattr('/mydir')
        self.assertTrue(stat.S_ISDIR(attr['st_mode']))
        entries = self.fs.readdir('/', None)
        self.assertIn('.', entries)
        self.assertIn('..', entries)
        self.assertIn('mydir', entries)

    def test_rmdir(self):
        self.fs.mkdir('/mydir', 0o755)
        self.fs.rmdir('/mydir')
        with self.assertRaises(FuseOSError):
            self.fs.getattr('/mydir')

    def test_rmdir_non_empty(self):
        self.fs.mkdir('/mydir', 0o755)
        self.fs.create('/mydir/file.txt', 0o644)
        with self.assertRaises(FuseOSError) as cm:
            self.fs.rmdir('/mydir')
        self.assertEqual(cm.exception.errno, errno.ENOTEMPTY)

    def test_rmdir_root_raises(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.rmdir('/')
        self.assertEqual(cm.exception.errno, errno.EBUSY)

    def test_readdir_on_file(self):
        self.fs.create('/test.txt', 0o644)
        with self.assertRaises(FuseOSError) as cm:
            self.fs.readdir('/test.txt', None)
        self.assertEqual(cm.exception.errno, errno.ENOTDIR)

    def test_readdir_lists_only_direct_children(self):
        self.fs.mkdir('/dir1', 0o755)
        self.fs.mkdir('/dir1/subdir', 0o755)
        self.fs.create('/dir1/subdir/deep.txt', 0o644)
        self.fs.create('/dir1/file.txt', 0o644)
        entries = self.fs.readdir('/dir1', None)
        self.assertIn('subdir', entries)
        self.assertIn('file.txt', entries)
        self.assertNotIn('deep.txt', entries)

    # ---------- rename ----------

    def test_rename_file(self):
        self.fs.create('/old.txt', 0o644)
        self.fs.write('/old.txt', b'data', 0, None)
        self.fs.rename('/old.txt', '/new.txt')
        with self.assertRaises(FuseOSError):
            self.fs.getattr('/old.txt')
        self.assertEqual(self.fs.read('/new.txt', 100, 0, None), b'data')

    def test_rename_dir_with_children(self):
        self.fs.mkdir('/dir1', 0o755)
        self.fs.create('/dir1/file.txt', 0o644)
        self.fs.rename('/dir1', '/dir2')
        self.assertEqual(self.fs.read('/dir2/file.txt', 100, 0, None), b'')

    def test_rename_nonexistent(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.rename('/no.txt', '/new.txt')
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    # ---------- chmod / chown / utimens ----------

    def test_chmod(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.chmod('/test.txt', 0o600)
        attr = self.fs.getattr('/test.txt')
        self.assertEqual(attr['st_mode'] & 0o777, 0o600)
        self.assertTrue(stat.S_ISREG(attr['st_mode']))

    def test_chmod_keeps_dir_flag(self):
        self.fs.mkdir('/mydir', 0o755)
        self.fs.chmod('/mydir', 0o700)
        attr = self.fs.getattr('/mydir')
        self.assertTrue(stat.S_ISDIR(attr['st_mode']))
        self.assertEqual(attr['st_mode'] & 0o777, 0o700)

    def test_chown(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.chown('/test.txt', 1234, 5678)
        attr = self.fs.getattr('/test.txt')
        self.assertEqual(attr['st_uid'], 1234)
        self.assertEqual(attr['st_gid'], 5678)

    def test_utimens(self):
        self.fs.create('/test.txt', 0o644)
        t = 1000000000.0
        self.fs.utimens('/test.txt', (t, t))
        attr = self.fs.getattr('/test.txt')
        self.assertAlmostEqual(attr['st_atime'], t, places=1)
        self.assertAlmostEqual(attr['st_mtime'], t, places=1)

    # ---------- open ----------

    def test_open_file(self):
        self.fs.create('/test.txt', 0o644)
        self.fs.open('/test.txt', os.O_RDONLY)

    def test_open_directory_raises(self):
        self.fs.mkdir('/mydir', 0o755)
        with self.assertRaises(FuseOSError) as cm:
            self.fs.open('/mydir', os.O_RDONLY)
        self.assertEqual(cm.exception.errno, errno.EISDIR)

    def test_open_nonexistent(self):
        with self.assertRaises(FuseOSError) as cm:
            self.fs.open('/no.txt', os.O_RDONLY)
        self.assertEqual(cm.exception.errno, errno.ENOENT)

    # ---------- Персистентность ----------

    def test_persistence_across_instances(self):
        """Данные сохраняются между двумя экземплярами SQLiteFS."""
        self.fs.create('/persist.txt', 0o644)
        self.fs.write('/persist.txt', b'persistent', 0, None)

        fs2 = SQLiteFS(self.tmp_db.name, uid=os.getuid(), gid=os.getgid())
        self.assertEqual(fs2.read('/persist.txt', 100, 0, None), b'persistent')
        self.assertEqual(fs2.getattr('/persist.txt')['st_size'], 10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
