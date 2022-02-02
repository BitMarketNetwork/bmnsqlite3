from __future__ import annotations
import abc
import logging
import pathlib
import random
import sqlite3
import unittest
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterable, List, Optional

import bmnsqlite3
from tests.wrappers import testdata as td
from tests import str_generator

log = logging.getLogger(__name__)

TEMP_DB_DIRECTORY = "tests/tmp"


def get_db_path(db_name: str) -> pathlib.Path:
    p = pathlib.Path(TEMP_DB_DIRECTORY).absolute()
    p.mkdir(parents=True, exist_ok=True)
    return p / db_name


def get_db_path_str(db_name: str) -> str:
    return get_db_path(db_name).resolve().as_posix()


def get_table_size(cursor: sqlite3.Cursor, table: str) -> int:
    return len(td.execute(cursor,
                          f"SELECT * FROM {table};").fetchall())


class ITestMixin(abc.ABC):
    persistent = False

    def __init__(self) -> None:
        # used to test origin sqlite3 behavior
        self.__skip_vfs = False
        self._db_path = None
        super().__init__()

    def skip_vfs(self) -> ITestMixin:
        self.__skip_vfs = True
        # for oneliner
        return self

    @property
    def _db_filesize(self) -> int:
        assert hasattr(self, "_db_path"), "There's no connection"
        if self._db_path.exists():
            return self._db_path.stat().st_size
        return -1

    def _name(self, case: unittest.TestCase) -> str:
        test_name = case.id().rpartition(".")[-1]
        return f"{test_name}_{self.__class__.__name__}"

    @contextmanager
    def connect(self, case: unittest.TestCase, erase_db: Optional[bool] = None,
                db_suffix: str = '', db_filename: str = None, **kwargs) -> sqlite3.Connection:
        if db_filename:
            assert not db_suffix
        if self.__skip_vfs:
            bmnsqlite3.vfs_register(None)
            log.info("Use origin sqlite3")
        else:
            case.assertTrue(self.validate(), "%s is invalid" %
                            self.__class__.__name__)
            bmnsqlite3.vfs_register(self, 1)
        case.assertIsInstance(self.persistent, bool,
                              "'peristent' must be attribute or property")
        if db_filename is None:
            if db_suffix:
                db_suffix = '_' + db_suffix
            db_filename = "%s%s.db" % (self._name(case), db_suffix)
        if erase_db is None:
            erase_db = not self.persistent
        if ":memory:" == db_filename:
            erase_db = False
        else:
            self._db_path = get_db_path(db_filename)
            db_filename = self._db_path.resolve().as_posix()
        if erase_db and self._db_path.exists():
            self._db_path.unlink()
            log.info("%s erased", db_filename)
        con = bmnsqlite3.connect(db_filename, **kwargs)
        yield con
        con.close()

    def test_base(self, case: unittest.TestCase) -> None:
        with self.connect(case) as con:
            c = con.cursor()
            c.execute(
                "CREATE TABLE IF NOT EXISTS monkies(id integer PRIMARY KEY, age INTEGER, name TEXT);")
            c.execute("INSERT INTO monkies(age, name) VALUES (23, 'Silly');")
            c.execute("INSERT INTO monkies(age, name) VALUES (167, 'Mighty');")
            con.commit()
            c.execute("SELECT * FROM monkies")
            monkeys = c.fetchall()
            con.commit()
            case.assertSetEqual(
                {(23, 'Silly'), (167, 'Mighty')}, {(age, name) for _, age, name in monkeys})
            c.close()

        with case.assertRaises(bmnsqlite3.ProgrammingError):
            con.commit()

    def test_readwrite(self, case: unittest.TestCase) -> None:
        data_size_factor = 1000

        def make_dragon(): return (str_generator(data_size_factor * 10),
                                   str_generator(data_size_factor * 4), random.random())

        with self.connect(case) as con:
            c = con.cursor()
            c.execute(
                "CREATE TABLE IF NOT EXISTS dragons(id integer PRIMARY KEY, data TEXT, name TEXT, height REAL);")
            first_dragon = make_dragon()
            c.execute(
                "INSERT INTO dragons(data, name, height) VALUES (?,?,?);", first_dragon)
            c.execute("SELECT * FROM dragons WHERE name=?;",
                      (first_dragon[1],))
            dragons = c.fetchall()
            case.assertTrue(dragons)
            case.assertEqual(
                dragons[0][1:],  # skip ID
                first_dragon,
            )
            second_dragon = make_dragon()
            c.execute(
                "INSERT INTO dragons(data, name, height) VALUES (?,?,?);", second_dragon)
            c.execute("SELECT * FROM dragons WHERE name=?;",
                      (first_dragon[1],))
            dragons = c.fetchall()
            case.assertEqual(
                dragons[0][1:],  # skip ID
                first_dragon,
            )
            c.execute("SELECT * FROM dragons WHERE name=?;",
                      (second_dragon[1],))
            dragons = c.fetchall()
            case.assertEqual(
                dragons[0][1:],  # skip ID
                second_dragon,
            )
            c.close()

    def test_heavy(self, case: unittest.TestCase,
                   count_factor: int = 3, length_factor: int = 10, middle_read: bool = False) -> None:
        """
        many huge writes to DB
        """
        with self.connect(case) as con:
            c = con.cursor()
            td.Stock.create(c, "Stocks")
            random.seed()
            stocks = [td.Stock.make(i * 3, length_factor)
                      for i in range(1, 100 * count_factor, 100)]

            def get(index: int) -> Iterable[tuple]:
                return (tuple(ss) for ss in stocks if ss.idx == index)

            second_store = set()
            # read/write queries
            for s in stocks:
                s.write(c)
                second_store.add(s)
                con.commit()
                if middle_read:
                    case.assertSetEqual(
                        second_store,
                        set(c.execute(
                            "SELECT * FROM td.Stocks;").fetchall()),
                    )
            ##
            con.commit()
            result = td.execute(c,
                                "SELECT * FROM Stocks WHERE idx=?;", (5,)).fetchall()
            case.assertSetEqual(
                set(result),
                set(get(5)),
            )

    def test_persistence(self, case: unittest.TestCase) -> None:
        table_name: str = "Stocks"
        with self.connect(case, True) as con:
            c = con.cursor()
            td.Stock.create(c, table_name)

            # there were crucial bug about opening file mode.. let's cover it
            case.assertEqual(get_table_size(c, table_name), 0)
            for i in range(10):
                td.Stock.make(i, 1).write(c)
            con.commit()
            case.assertEqual(c.lastrowid, 10)
            case.assertEqual(
                get_table_size(c, table_name), 10
            )
            c.close()
        # reopen it
        with self.connect(case, False) as con:
            c = con.cursor()
            case.assertEqual(
                get_table_size(c, table_name), 10
            )
            for i in range(5):
                td.Stock.make(i, 1).write(c)
            case.assertEqual(c.lastrowid, 15)
            case.assertEqual(
                get_table_size(c, table_name), 15
            )
            # remove some and check again
            td.execute(
                c, f"DELETE FROM {table_name} WHERE idx = ?;", (12,))
            td.Stock.make(10, 1).write(c)
            case.assertEqual(c.lastrowid, 16)
            case.assertIn(
                get_table_size(c, table_name), (15, 16)
            )
            c.close()

    def test_vacuum(self, case: unittest.TestCase) -> None:
        """
        tests many tables and vacuum command
        """
        table_names: List[str] = [f"Stocks{i}" for i in range(10)]
        with self.connect(case, True) as con:
            c = con.cursor()
            for t in table_names:
                td.Stock.create(c, t)
                for i in range(100):
                    td.Stock.make(i, 1).write(c)
            for t in table_names:
                td.execute(c, f"DELETE FROM {t};")
            con.commit()
            c.execute("VACUUM")
            c.close()

    def test_foreign_key_support(self, case: unittest.TestCase) -> None:
        """o2m"""
        table_names: List[str] = ["Stocks", "Transactions"]
        with self.connect(case, True) as con:
            c = con.cursor()
            td.execute(c, "PRAGMA foreign_keys = OFF;")
            td.Stock.create(c, table_names[0])
            td.Transaction.create(c, table_names[1])
            td.Stock.make(1, 10).write(c)
            # must fail ONLY with FK support
            td.Transaction.make(123, 100).write(c)
            c.close()
        with self.connect(case, True) as con:
            c = con.cursor()
            td.execute(c, "PRAGMA foreign_keys = ON;")
            td.Stock.create(c, table_names[0])
            td.Transaction.create(c, table_names[1])
            with case.assertRaises(bmnsqlite3.IntegrityError):
                td.Transaction.make(190, 100).write(c)
            last_s = td.Stock.make(1, 10).write(c)
            case.assertEqual(last_s.id, c.lastrowid)
            last_t1 = td.Transaction.make(909302, last_s.idx).write(c)
            last_t2 = td.Transaction.make(88, last_s.idx).write(c)
            with case.assertRaises(bmnsqlite3.IntegrityError):
                td.execute(c,
                           f"UPDATE {table_names[1]} SET stock = 102 WHERE description = ?;", last_t1.description)
            with case.assertRaises(bmnsqlite3.IntegrityError):
                last_s.delete(c, 'title')
            # delete relative transactions
            last_t1.delete(c, 'description')

            # TODO:
            # with case.assertRaises(bmnsqlite3.IntegrityError):
            #     last_s.delete(c, 'title')

            last_t2.delete(c, 'description')
            last_s.delete(c, 'title')
            c.close()

    def test_many_connections(self, case: unittest.TestCase) -> None:
        # TODO: improve ... read and match
        table_name: str = "stocks"
        with self.connect(case, db_suffix="1", erase_db=True) as con1:
            c1 = con1.cursor()
            with self.connect(case, db_suffix="2", erase_db=True) as con2:
                c2 = con2.cursor()
                with self.connect(case, db_suffix="3", erase_db=True) as con3:
                    c3 = con3.cursor()
                    td.Stock.create(c1, table_name)
                    td.Stock.create(c2, table_name)
                    td.Stock.create(c3, table_name)
                    td.Stock.make(1, 10).write(c1)
                    td.Stock.make(1, 10).write(c2)
                    td.Stock.make(1, 10).write(c3)
                    con1.commit()
                    con2.commit()
                    con3.commit()

    def test_foreign_key_support_simplified(self, case: unittest.TestCase) -> None:
        table_names: List[str] = ["Stocks", "Transactions"]
        with self.connect(case, True) as con:
            c = con.cursor()
            td.execute(c, "PRAGMA foreign_keys = ON;")
            td.Stock.create(c, table_names[0])
            td.Transaction.create(c, table_names[1])
            last_s = td.Stock.make(1, 10).write(c)
            last_t1 = td.Transaction.make(23, last_s.idx).write(c)
            td.Transaction.make(90, last_s.idx).write(c)
            # delete relative transactions
            last_t1.delete(c, 'description')
            with case.assertRaises(bmnsqlite3.IntegrityError):
                last_s.delete(c, 'title')
            c.close()

    def test_foreign_key_deletion(self, case: unittest.TestCase) -> None:
        table_names: List[str] = ["Stocks", "Transactions"]
        with self.connect(case, True) as con:
            c = con.cursor()
            td.execute(c, "PRAGMA foreign_keys = ON;")
            td.Stock.create(c, table_names[0])
            td.Transaction.create(c, table_names[1], 'CASCADE')
            last_s = td.Stock.make(1, 10).write(c)
            td.Transaction.make(1, last_s.idx).write(c)
            last_s.delete(c, 'description')
            case.assertEqual(get_table_size(c, table_names[1]), 0)
            c.close()
        with self.connect(case, True, 'set_null') as con:
            c = con.cursor()
            td.execute(c, "PRAGMA foreign_keys = ON;")
            td.Stock.create(c, table_names[0])
            td.Transaction.create(c, table_names[1], 'SET NULL')
            last_s = td.Stock.make(2, 10).write(c)
            td.Transaction.make("dummy", last_s.idx).write(c)
            with case.assertRaises(bmnsqlite3.IntegrityError):
                last_s.delete(c, 'description')
            c.close()

    def test_uniqueness(self, case: unittest.TestCase) -> None:
        table_name: str = "stocks"
        with self.connect(case, True) as con:
            c = con.cursor()
            td.Stock.create(c, table_name)
            s1 = td.Stock.make(1, 10).write(c)
            with case.assertRaises(bmnsqlite3.IntegrityError):
                td.Stock.make(1, 10, idx=s1.idx).write(c)
            c.close()

    def test_memory_tables(self, case: unittest.TestCase) -> None:
        table_name: str = "stocks"
        with self.connect(case, db_filename=":memory:") as con:
            c = con.cursor()
            td.Stock.create(c, table_name)
            s1 = td.Stock.make(1, 1).write(c)
            case.assertEqual(s1, s1.get_me(c, "title"))
            c.close()

    def test_columns_by_index(self, case: unittest.TestCase) -> None:
        with self.connect(case, True) as con:
            con.row_factory = bmnsqlite3.Row
            c = con.cursor()
            td.execute(c, "create table person(firstname, age)")
            td.execute(c, "select 'John' as name, 42 as age")
            for row in c:
                assert row[0] == row["name"]
                assert row["name"] == row["nAmE"]
                assert row[1] == row["age"]
                assert row[1] == row["AgE"]
            c.close()

    def test_executescript(self, case: unittest.TestCase) -> None:
        with self.connect(case) as con:
            c = con.cursor()
            c.executescript(
                """
                create table if not exists  person(firstname, age);
                insert into person values('John',42);
                insert into person values('Eva',45);
                """
            )
            r = c.execute("select firstname from person where age = 45;")
            case.assertEqual(
                r.fetchone()[0],
                'Eva',
            )
            c.close()

    def test_adapters(self, case: unittest.TestCase) -> None:

        with self.connect(case) as con:
            # via protocol
            class PointA(td.Point):
                pass

            PointA.test_adapter(con.cursor(), case)

            # via callable
            class PointB(td.Point):
                pass

            bmnsqlite3.register_adapter(PointB, PointB.adapt)
            PointB.test_adapter(con.cursor(), case)

    def test_converters(self, case: unittest.TestCase) -> None:
        # test both approaches:  PARSE_DECLTYPES and PARSE_COLNAMES
        class PointC(td.Point):
            pass

        # Register the adapter
        bmnsqlite3.register_adapter(PointC, PointC.adapt)

        # Register the converter
        bmnsqlite3.register_converter("pointc", PointC.convert)

        #########################
        # 1) Using declared types
        p = PointC()
        with self.connect(case, erase_db=True,
                          detect_types=sqlite3.PARSE_DECLTYPES) as con:
            c = con.cursor()
            c.execute("create table testc1(p pointc)")
            c.execute("insert into testc1(p) values (?)", (p,))
            c.execute("select p from testc1")
            case.assertEqual(c.fetchone()[0], p)
            c.close()

        #######################
        # 1) Using column names
        p = PointC()
        with self.connect(case,
                          detect_types=sqlite3.PARSE_COLNAMES) as con:
            c = con.cursor()
            c.execute("create table testc2(p)")

            c.execute("insert into testc2(p) values (?)", (p,))
            c.execute('select p as "p [pointc]" from testc2')
            case.assertEqual(c.fetchone()[0], p)
            c.close()

    def test_default_adapters_converters(self, case: unittest.TestCase) -> None:
        with self.connect(case,
                          erase_db=True, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as con:
            c = con.cursor()
            td.execute(
                c, "CREATE TABLE test(d date, ts timestamp)")

            today = date.today()
            now = datetime.utcnow()

            td.execute(c, "INSERT INTO test(d, ts) VALUES (?, ?)", (today, now))
            td.execute(c, "SELECT d, ts fROM test")
            row = c.fetchone()
            case.assertIsInstance(row[0], date)
            case.assertEqual(row[0], today)
            case.assertIsInstance(row[1], datetime)
            case.assertEqual(row[1], now)

            c.execute(
                'SELECT current_date AS "d [date]", current_timestamp AS "ts [timestamp]"')
            row = c.fetchone()
            case.assertIsInstance(row[0], date)
            case.assertIsInstance(row[1], datetime)
            c.close()

    def test_create_function(self, case: unittest.TestCase) -> None:
        import hashlib

        def md5sum(t: bytes) -> str:
            return hashlib.md5(t).hexdigest()

        with self.connect(case) as con:
            con.create_function("md5", 1, md5sum)
            c = con.cursor()
            c.execute("select md5(?)", (b"foo",))
            case.assertEqual(c.fetchone()[0], md5sum(b"foo"))
            c.close()

    def test_create_function_determistic(self, case: unittest.TestCase) -> None:
        import random

        def rnd(low: int, high: int) -> int:
            return random.randint(low, high)

        with self.connect(case) as con:
            con.create_function("rnd", 2, rnd, deterministic=True)
            cur = con.cursor()
            cur.execute("select rnd(?,?)", (100, 1000))
            case.assertEqual(cur.fetchone()[0], rnd(100, 1000))
            cur.close()

    def test_create_aggregate(self, case: unittest.TestCase) -> None:
        class MySum:
            def __init__(self):
                self.count = 0

            def step(self, value):
                self.count += value

            def finalize(self):
                return self.count

        with self.connect(case, erase_db=True) as con:
            con.create_aggregate("mysum", 1, MySum)
            c = con.cursor()
            c.execute("create table test(i)")
            c.execute("insert into test(i) values (11)")
            c.execute("insert into test(i) values (20)")
            c.execute("select mysum(i) from test")
            case.assertEqual(c.fetchone()[0], 11 + 20)
            c.close()

    def test_create_collation(self, case: unittest.TestCase) -> None:
        def collate_reverse(string1: str, string2: str) -> int:
            if string1 == string2:
                return 0
            if string1 < string2:
                return 1
            return -1

        with self.connect(case, erase_db=True) as con:
            con.create_collation("reverse", collate_reverse)
            c = con.cursor()
            letters = [(ll,) for ll in "2021Collation"]
            c.execute("create table test(x)")
            c.executemany("insert into test(x) values (?)", letters)
            c.execute("select x from test order by x collate reverse")
            letters.sort(reverse=True)
            case.assertEqual(letters, list(c))
            c.close()

    def test_text_factory(self, case: unittest.TestCase) -> None:
        with self.connect(case, erase_db=True) as con:
            c = con.cursor()
            austria = "\xd6sterreich"
            c.execute("select ?", (austria,))
            row = c.fetchone()
            case.assertEqual(row[0], austria)

            con.text_factory = bytes
            c.execute("select ?", (austria,))
            row = c.fetchone()
            case.assertIsInstance(row[0], bytes)
            case.assertEqual(row[0], austria.encode("utf-8"))

            con.text_factory = lambda x: x.decode("utf-8") + "foo"
            c.execute("select ?", ("bar",))
            row = c.fetchone()
            case.assertEqual(row[0], "barfoo")
            c.close()

    def test_iterdump(self, case: unittest.TestCase) -> None:
        dump_sql_path = get_db_path_str('dump.sql')
        with self.connect(case, erase_db=True) as con:
            c = con.cursor()
            td.Stock.create(c, "stocks_dump")
            td.Stock.make(1, 10).write(c)
            c.close()
            with open(dump_sql_path, 'w') as f:
                for line in con.iterdump():
                    f.write('%s\n' % line)
        # match
        with self.connect(case, erase_db=True, db_suffix="result") as con:
            c = con.cursor()
            with open(dump_sql_path, 'r') as f:
                c.executescript(f.read())
            c.close()

    def test_backup(self, case: unittest.TestCase) -> None:
        table_name = "stocks_bkp"
        fresh_start = True
        leftover = 1

        def progress(_, remaining, __):
            nonlocal leftover
            leftover = remaining
        with self.connect(case, db_suffix='src', erase_db=fresh_start) as source:
            c = source.cursor()
            td.Stock.create(c, table_name)
            s1 = td.Stock.make(1, 10).write(c)
            c.close()
            with self.connect(case, db_suffix='trg', erase_db=fresh_start) as target:
                source.backup(target, pages=1, progress=progress)
        case.assertEqual(leftover, 0)
        with self.connect(case, db_suffix='trg') as con:
            case.assertEqual(s1.get_me(con.cursor(), 'title'), s1)

    def test_isolation_level(self, case: unittest.TestCase) -> None:
        table_name = "Stocks"
        with self.connect(case, erase_db=True, isolation_level="DEFERRED") as con:
            c = con.cursor()
            td.Stock.create(c, table_name)
            s1 = td.Stock.make(1, 1).write(c)
            case.assertEqual(s1, s1.get_me(c, "title"))
            s1.update(c, 'title', description='foobar')
            case.assertEqual(('foobar',), s1.get(c, 'title', 'description'))
            c.close()

    def test_all(self, case: unittest.TestCase, *, skip_vacuum=True, skip_heavy = False) -> None:
        self.test_base(case)
        self.test_readwrite(case)

        # two times intentionally
        self.test_persistence(case)
        self.test_persistence(case)

        if not skip_vacuum:
            self.test_vacuum(case)

        # TODO: both XOR failed.. very strange case. will be explored in separate test file
        # self.test_backup(case)

        self.test_foreign_key_support(case)
        self.test_many_connections(case)
        self.test_foreign_key_deletion(case)
        self.test_columns_by_index(case)
        self.test_memory_tables(case)
        self.test_executescript(case)
        self.test_adapters(case)
        self.test_converters(case)
        self.test_create_function(case)
        self.test_create_aggregate(case)
        self.test_create_collation(case)
        self.test_text_factory(case)
        self.test_isolation_level(case)

        self.test_default_adapters_converters(case)
        self.test_iterdump(case)

        if not skip_heavy:
            self.test_heavy(case)

        # noinspection PyTypeChecker
        if sqlite3.version_info > (3, 8, 3):
            self.test_create_function_determistic(case)

    def validate(self) -> bool:
        return True
