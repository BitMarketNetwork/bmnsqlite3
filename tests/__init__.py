import abc
import logging
import pathlib
import random
import string
import sys
import traceback
import unittest
from typing import Any, Optional, Type

import bmnsqlite3

log = logging.getLogger(__name__)

UNRAISABLE_FULL_SUPPORT = sys.version_info >= (3, 8,)
MS_WINDOWS = (sys.platform == 'win32')

if UNRAISABLE_FULL_SUPPORT:
    UNRAISABLE_ARGS_TYPE = 'sys.UnraisableHookArgs'
else:
    """
    Test coverage is not complete in this case
    """
    UNRAISABLE_ARGS_TYPE = Any


def only_windows(fun):
    return unittest.skipIf(not MS_WINDOWS, "Windows sqlite backend required")(fun)

# TODO: silly impl


def only_unix(fun):
    return unittest.skipIf(MS_WINDOWS, "Unix sqlite backend required")(fun)


class TracebackHelper:

    def __init__(self, tb: traceback, top: bool = True) -> None:
        self.__tb: traceback = tb
        self.__top: bool = top

    @classmethod
    def from_hook(cls, args: UNRAISABLE_ARGS_TYPE) -> 'TracebackHelper':
        return TracebackHelper(args.exc_traceback)

    def __str__(self) -> str:
        return self.__tb.tb_frame.f_code.co_name

    def __repr__(self) -> str:
        return str(self.__tb.tb_frame)

    def __iter__(self) -> 'TracebackHelper':
        return self

    def __next__(self) -> 'TracebackHelper':
        if self.__top:
            self.__top = False
        else:
            self.__tb = self.__tb.tb_next
            if not self.__tb:
                raise StopIteration
        return self


class DbPathMixin(abc.ABC):
    scope = None

    def db_path(self, name: Optional[str] = None, *,
                vfs: Optional[str] = None,
                prefix: Optional[str] = None,
                uri_format: bool = False) -> str:
        from tests.wrappers.testcases import get_db_path
        name = name or self.id().rpartition('.')[-1].lower()
        if prefix:
            name = prefix.lower() + "_" + name
        if not name.endswith(".db"):
            name += ".db"
        self._db_path = get_db_path(f"{self.scope}_{name}")
        if vfs is not None:
            uri_format = True
        if not uri_format:
            return self._db_path.resolve().as_posix()
        """
        Convert all "?" characters into "%3f".
        Convert all "#" characters into "%23".
        On windows only, convert all "\" characters into "/".
        Convert all sequences of two or more "/" characters into a single "/" character.
        On windows only, if the filename begins with a drive letter, prepend a single "/" character.
        Prepend the "file:" scheme.
        """
        uri = self._db_path.resolve().as_posix()
        uri.replace("\\", "/")
        log.warning(uri)
        # TODO:
        if vfs is None:
            return f"file:/{uri}"
        return f"file:/{uri}?vfs={vfs}"

    def db_size(self, path: Optional[str] = None) -> int:
        if path:
            return pathlib.Path(path).stat().st_size
        return self._db_path.stat().st_size

    def erase_db(self) -> None:
        if getattr(self, "_db_path", None):
            try:
                kwargs = {}
                if sys.version_info >= (3, 8):
                    kwargs.update({'missing_ok': True})
                self._db_path.unlink(**kwargs)
            except (PermissionError, FileNotFoundError):
                # FileNotFoundError only for 3.7 support
                pass

    @staticmethod
    def total_clear() -> None:
        """
        removes all *.db files
        """
        from tests.wrappers.testcases import TEMP_DB_DIRECTORY
        for file in pathlib.Path(TEMP_DB_DIRECTORY).absolute().glob("*.db"):
            file.unlink()


class SqlCheckTestCase(unittest.TestCase, DbPathMixin):
    """
    TestCase that implements some sql operations
    """

    def _db_write(self, con: bmnsqlite3.Connection) -> None:
        c = con.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS monkies(id INTEGER PRIMARY KEY, age INTEGER, name TEXT, ts TIMESTAMP);")
        c.execute(
            "INSERT INTO monkies(age, name, ts) VALUES (23, 'Silly', current_timestamp);")
        c.execute("INSERT INTO monkies(age, name, ts) VALUES (167, 'Mighty', ?);",
                  (bmnsqlite3.Timestamp(2004, 2, 14, 7, 15, 0),))
        con.commit()
        self._db_write_check(con=con)

    def _db_write_check(self, con: bmnsqlite3.Connection) -> None:
        c = con.cursor()
        c.execute("SELECT DATE('now');")
        c.execute("SELECT datetime(1092941466, 'unixepoch', 'localtime');")
        c.execute("SELECT julianday('now');")
        c.execute("SELECT age, name FROM monkies")
        monkeys = c.fetchall()
        c.close()
        if (23, 'Silly') not in monkeys or (167, 'Mighty') not in monkeys:
            raise RuntimeError("DB fetch failure")

    def _do_vacuum(self, con: bmnsqlite3.Connection, complexity: int = 100) -> None:
        """
        complexity must be big anough to make sqlite run DB truncation
        """

        def entry_count(c: bmnsqlite3.Cursor, table: str) -> int:
            c.execute(f"SELECT * FROM {table};")
            return len(c.fetchall())

        def run_table(c: bmnsqlite3.Cursor, table: str) -> None:
            c.execute(f"CREATE TABLE IF NOT EXISTS {table}(i TEXT);")
            for i in range(complexity):
                c.execute(
                    f"INSERT INTO {table} values(?);", (f"+{i}" * complexity,))
            self.assertEqual(entry_count(c, table=table), complexity)
            c.execute(f"DELETE FROM {table};")
            self.assertEqual(entry_count(c, table=table), 0)
        c = con.cursor()
        run_table(c, "vacuum_test")
        con.commit()
        c.execute("VACUUM")

    def _do_random(self, con: bmnsqlite3.Connection) -> None:
        c = con.cursor()
        c.execute("SELECT RANDOMBLOB(16);")
        con.commit()

    def discover_exception(self, func: Optional[callable]) -> callable:
        """
        wrap hook only for testing
        """

        def wrapper(*args):
            try:
                if func:
                    func(*args)
                self._hook_called = True
            except unittest.TestCase.failureException as fe:
                self._exception = fe

        return wrapper

    def check_connect(self, w: Any, hook: Optional[callable] = None, *,
                      exception: Type[Exception] = bmnsqlite3.ProgrammingError,
                      exception_message: Optional[str] = None) -> None:
        # warning !!! in real coding assign it directly
        # sys.unraisablehook = error_hook
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with self.assertRaises(expected_exception=exception):
            with bmnsqlite3.connect(self.db_path()) as ex:
                pass
            if exception_message:
                self.assertEqual(str(ex.exception), exception_message)
        if hook:
            self.assertUnraisableCalled()

    def check_connect_silent(self, w: Any, hook: Optional[callable] = None) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        bmnsqlite3.connect(self.db_path())
        if hook:
            self.assertUnraisableCalled()

    def check_write(self, w: Any, hook: Optional[callable] = None, *, exception: Any = bmnsqlite3.ProgrammingError,
                    exception_message: Optional[str] = None, **kwargs) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with self.assertRaises(expected_exception=exception) as ex:
            with bmnsqlite3.connect(self.db_path(), **kwargs) as con:
                self._db_write(con)
            if exception_message:
                self.assertEqual(str(ex.exception), exception_message)
        if hook:
            self.assertUnraisableCalled()

    def check_vacuum(self, w: Any, hook: Optional[callable] = None, *, exception: Any = bmnsqlite3.ProgrammingError,
                     exception_message: Optional[str] = None, **kwargs) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with bmnsqlite3.connect(self.db_path(), **kwargs) as con:
            with self.assertRaises(expected_exception=exception) as ex:
                self._do_vacuum(con)
            if exception_message:
                self.assertEqual(str(ex.exception), exception_message)
        if hook:
            self.assertUnraisableCalled()

    def check_write_silent(self, w: Any, hook: Optional[callable] = None, **kwargs) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with bmnsqlite3.connect(self.db_path(), **kwargs) as con:
            self._db_write(con)
        if hook:
            self.assertUnraisableCalled()

    def check_vacuum_silent(self, w: Any, hook: Optional[callable] = None, **kwargs) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with bmnsqlite3.connect(self.db_path(), **kwargs) as con:
            self._do_vacuum(con)
        if hook:
            self.assertUnraisableCalled()

    def check_random_silent(self, w: Any, hook: Optional[callable] = None, **kwargs) -> None:
        sys.unraisablehook = self.discover_exception(hook)
        bmnsqlite3.vfs_register(w, make_default=True)
        with bmnsqlite3.connect(self.db_path(w.__class__.__name__), **kwargs) as con:
            self._do_random(con)
        if hook:
            self.assertUnraisableCalled()

    def check_connect_warns(self, w: Any, regex: Optional[str] = None) -> None:
        bmnsqlite3.vfs_register(w, make_default=True)
        with self.assertWarnsRegex(bmnsqlite3.WrapperWarning, expected_regex=regex):
            with bmnsqlite3.connect(self.db_path()):
                pass

    def check_write_warns(self, w: Any, regex: Optional[str] = None) -> None:
        bmnsqlite3.vfs_register(w, make_default=True)
        with self.assertWarnsRegex(bmnsqlite3.WrapperWarning, expected_regex=regex):
            with bmnsqlite3.connect(self.db_path()) as con:
                self._db_write(con)

    def check_vacuum_warns(self, w: Any, regex: Optional[str] = None) -> None:
        bmnsqlite3.vfs_register(w, make_default=True)
        with self.assertWarnsRegex(bmnsqlite3.WrapperWarning, expected_regex=regex):
            with bmnsqlite3.connect(self.db_path()) as con:
                self._do_vacuum(con)

    def assertExceptionLocation(self, wrapper: Any, method: str) -> None:
        if hasattr(wrapper, "exception_location"):
            self.assertEqual(method, wrapper.exception_location)

    def setUp(self) -> None:
        super().setUp()
        self._exception = None
        self._hook_called = False

    def tearDown(self) -> None:
        super().tearDown()
        self._hook_called = False
        if self._exception:
            raise self._exception

    def resetHookCall(self) -> None:
        self._hook_called = False

    def assertUnraisableNotCalled(self) -> None:
        if UNRAISABLE_FULL_SUPPORT and self._hook_called:
            self.fail("Unraisable hook has called")

    def assertUnraisableCalled(self) -> None:
        if UNRAISABLE_FULL_SUPPORT and not self._hook_called:
            self.fail("Unraisable hook hasn't called")


def str_generator(size: int, chars=string.ascii_uppercase + string.digits) -> str:
    return ''.join(random.choice(chars) for _ in range(size))


def randbytes(n: int) -> bytes:
    return bytes(map(random.getrandbits, (8,) * n))


def gc_collect():
    """Force as many objects as possible to be collected.

    In non-CPython implementations of Python, this is needed because timely
    deallocation is not guaranteed by the garbage collector.  (Even in CPython
    this can be the case in case of reference cycles.)  This means that __del__
    methods may be called later than expected and weakrefs may remain alive for
    longer than expected.  This function tries its best to force all garbage
    objects to disappear.
    """
    import gc
    gc.collect()
    gc.collect()
    gc.collect()
