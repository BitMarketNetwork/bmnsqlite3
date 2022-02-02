
from io import SEEK_SET
import logging
import os
from tests import wrappers
from tests.wrappers.testcases import get_db_path
import unittest
from typing import Any, Type, Union, Optional, List
from bmnsqlite3 import vfs
import bmnsqlite3
from tests import DbPathMixin
from tests.wrappers import full, crypto, abstract
import tests.wrappers.testdata as td

log = logging.getLogger(__name__)

@unittest.skip("For development only")
class VacuumTestCase(unittest.TestCase, DbPathMixin):
    scope = "vacuum"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.total_clear()

    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.erase_db()

    def run_vacuum_2(self, wrapper: Any) -> None:
        bmnsqlite3.vfs_register(wrapper)
        table_names: List[str] = ["Stocks1", "Stocks2"]  # , "Stocks3"]
        with bmnsqlite3.connect(self.db_path()) as con:
            c = con.cursor()
            for t in table_names:
                td.Stock.create(c, t)
                for i in range(2):
                    td.Stock.make(i, 1).write(c)
            for t in table_names:
                td.execute(c, f"DELETE FROM {t};")
            con.commit()
            c.execute("VACUUM")
            c.close()

    def run_vacuum(self, wrapper: Any) -> None:
        bmnsqlite3.vfs_register(wrapper)
        count = 100

        def entry_count(c: bmnsqlite3.Cursor, table: str = 'sample') -> int:
            c.execute(f"SELECT * FROM {table};")
            return len(c.fetchall())

        def run_table(c: bmnsqlite3.Cursor, table: str = 'sample') -> None:
            c.execute(f"CREATE TABLE IF NOT EXISTS {table}(i TEXT);")
            for i in range(count):
                c.execute(
                    f"INSERT INTO {table} values(?);", (f"+{i}" * count,))
            self.assertEqual(entry_count(c, table=table), count)
            c.execute(f"DELETE FROM {table};")
            self.assertEqual(entry_count(c, table=table), 0)

        def run_connection(filename: str = "sample", recursion: int = 3):
            with bmnsqlite3.connect(self.db_path(filename)) as con:
                c = con.cursor()
                for table in tables:
                    run_table(c, table)
                con.commit()
                c.execute("VACUUM")
                # enforce to the top
                if recursion:
                    run_connection(filename + "_scopped", recursion - 1)

        tables = [f"sample_{i}" for i in range(10)]
        db_files = [f"c_{i}" for i in range(3)]
        for db in db_files:
            run_connection(db)
        # run_connection()
        self.assertTrue(wrapper.truncate_called)


    def test_custom_wrapper(self_):

        class CW(abstract.Base64Mixin, crypto.ISectorWrapper):
            SECTOR_SIZE = 4096
            RATIO = 2

            def __init__(self) -> None:
                super().__init__()
                self.write_offsets = set()
                self.read_offsets = set()

            def write(self, fh: Any, data: bytes, offset: int) -> None:
                if fh.encode:
                    self.write_offsets.add((
                        len(data), offset))
                    self_.assertEqual(0, (offset * self.RATIO) %
                                      self.SECTOR_SIZE)
                return super().write(fh, data, offset)

            def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
                if not fh.encode:
                    return super().read(fh, length, offset)
                self.read_offsets.add(offset * self.RATIO)
                try:
                    return super().read(fh, length=length, offset=offset)
                except abstract.DecodeError as de:
                    offsets = [off for _, off in self.write_offsets]
                    log.warning(de)
                    self_.assertEqual(de.data, b'\x00' * de.length)
                    self_.assertIn(offset, offsets,
                                   f"{fh.filename} //read {length} at {offset}: => {self.write_offsets}")

            def truncate(self, fh: Any, size: int) -> None:
                log.warning("Truncate to %s", size)
                return super().truncate(fh, size)

            def decrypt(self, data: bytes, **kwargs) -> bytes:
                if all(0 == int(i) for i in data):
                    return data
                log.warning("==> %d", data[0])
                return super().decrypt(data, **kwargs)

            def make_fill_data(self, length: int) -> bytes:
                return b'0' * length

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0x10 + 0x400

        CW().test_vacuum(self_)
