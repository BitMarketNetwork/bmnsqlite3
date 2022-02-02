import logging
import random
import sys
import unittest
from typing import Optional, Tuple

import bmnsqlite3
from tests.wrappers import full, partial
from tests.wrappers.testcases import get_db_path

RANDOM_WRAPPER = True

log = logging.getLogger(__name__)
wrappers = (
    # crypto.ZipIoWrapper,
    # full.XorIoWrapper,
    # full.XorMixIoWrapper,
    # partial.FernetPartialIoWrapper,
    # crypto.FernetIoWrapper,
    # partial.XorPartialIoWrapper,
    partial.UselessPartialIoWrapper,
    full.UselessWrapper,
)
current_wrapper = None
current_test_id = None

def todo_for_python3_version(*args):
    if not args:
        return unittest.skip("TODO")
    py = (sys.version_info.major,sys.version_info.minor)
    return unittest.skipIf(any( py == (3,a) for a in args ), "TODO")


class BmnTestCase(unittest.TestCase):

    def _connect(self, db_filename: Optional[str] = None, erase_db: bool = True,
                 memory_table: bool = False, shift_wrapper: bool = True, **kwargs):
        self.assertIsInstance(db_filename, (str, type(None)))
        self.assertIsInstance(erase_db, bool)
        self.assertIsInstance(memory_table, bool)
        if RANDOM_WRAPPER:
            random.seed()
        if memory_table:
            self.assertFalse(db_filename)
        if not db_filename:
            if memory_table:
                db_filename = ":memory:"
            else:
                global current_test_id
                test_name = f"{self.__class__.__name__}_{self.id().rpartition('.')[-1]}".lower(
                )
                # test_name = self.id().partition('origin.')[-1].lower()
                # test_name = self.id().partition('.')[-1].partition('.')[-1].lower()
                # test_name = self.id().rpartition('.')[-1].lower()
                # this happens when connection is doubled ( in setUp and in test function locally )
                if test_name == current_test_id:
                    test_name += "_local"
                db_filename = f"sqlite_{test_name}.db"
                current_test_id = test_name
        if shift_wrapper:
            try:
                bmnsqlite3.vfs_register(self.__next_wrapper(RANDOM_WRAPPER))
            except bmnsqlite3.WrapperError as ce:
                self.assertIn("new wrapper", str(ce))
        if not memory_table:
            self._db_path = get_db_path(db_filename)
            if erase_db and self._db_path.exists():
                try:
                    self._db_path.unlink()
                except PermissionError:
                    pass
            db_filename = self._db_path.resolve().as_posix()
        self.assertIsNotNone(bmnsqlite3.vfs_find())
        try:
            return bmnsqlite3.connect(
                db_filename,
                **kwargs
            )
        except bmnsqlite3.OperationalError as oe:
            log.error("Connection error: %s with %s", oe, db_filename)
            raise oe from oe

    def setUp(self) -> None:
        super().setUp()

    @classmethod
    def setUpClass(cls) -> None:
        pass

    def __next_wrapper(self, rnd: bool):
        if rnd:
            return random.choice(wrappers)()
        global current_wrapper
        if not current_wrapper:
            current_wrapper = iter(wrappers)
        try:
            return next(current_wrapper)()
        except StopIteration:
            current_wrapper = None
            return self.__next_wrapper(rnd=rnd)
