import logging
import random
import unittest
from typing import Any, Tuple, Union, Optional

import bmnsqlite3
from tests import SqlCheckTestCase, DbPathMixin, MS_WINDOWS
from tests.wrappers import full, minimal, partial, crypto, abstract

log = logging.getLogger(__name__)

HAS_CONNECTION_COUNT = hasattr(bmnsqlite3, "connection_count")

WRAPPERS_TO_TEST = [
    full.UselessWrapper(),
    partial.UselessPartialIoWrapper(),
    None,  # unregister
]
# from 1 to 100 or more
TEST_COMPLEXITY = 50


class UsageTestCase(unittest.TestCase, DbPathMixin):
    scope = "usage"

    def setUp(self) -> None:
        return super().setUp()

    @classmethod
    def setUpClass(cls) -> None:
        random.seed()

    @staticmethod
    def nextWrapper() -> Any:
        return random.choice(WRAPPERS_TO_TEST)

    def test_open_close(self) -> None:
        connections = []
        for i in range(TEST_COMPLEXITY):
            while True:
                try:
                    w = self.nextWrapper()
                    bmnsqlite3.vfs_register(w)
                    break
                except bmnsqlite3.OperationalError:
                    # it is expected behavior
                    connections.pop().close()
                except bmnsqlite3.DatabaseError as de:
                    log.error(de)
                    raise de from de

            db_path_ = self.db_path()
            connections.append(bmnsqlite3.connect(db_path_))
            for _ in range(random.randint(0, i)):
                c = random.choice(connections)
                c.close()


class GetVFSTestCase(unittest.TestCase, DbPathMixin):

    def setUp(self) -> None:
        super().setUp()
        bmnsqlite3.vfs_register(None)

    def tearDown(self) -> None:
        super().tearDown()
        bmnsqlite3.vfs_register(None)

    def test_base(self):
        self.assertIsNone(bmnsqlite3.vfs_find())
        w = full.UselessWrapper()
        bmnsqlite3.vfs_register(w)
        self.assertEqual(w, bmnsqlite3.vfs_find())
        bmnsqlite3.vfs_register(None)
        self.assertIsNone(bmnsqlite3.vfs_find())

    def test_kwargs(self):
        w = full.UselessWrapper()
        bmnsqlite3.vfs_register(wrapper=w)
        self.assertEqual(w, bmnsqlite3.vfs_find())
        with self.assertRaises(TypeError):
            bmnsqlite3.vfs_register(_wrapper=w)

    def test_default(self):
        bmnsqlite3.vfs_register(wrapper=None)
        self.assertIs(None, bmnsqlite3.vfs_find())

        class Wrapper(full.UselessWrapper):

            def open(self, path: str, flags: int) -> Any:
                raise RuntimeError("error")

        w1 = Wrapper()
        bmnsqlite3.vfs_register(wrapper=w1, make_default=0)
        # there is no support 'make_default = 0' yet
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            bmnsqlite3.connect(self.db_path())

    def test_vfs_chain(self):
        """
        TODO: this behavior will be changed n future
        """

        class W1(full.UselessWrapper):
            pass

        class W2(full.UselessWrapper):
            pass

        class W3(full.UselessWrapper):
            pass

        w1 = W1()
        w3 = W3()
        self.assertIsNone(bmnsqlite3.vfs_find())
        bmnsqlite3.vfs_register(w1, make_default=1)
        self.assertIs(w1, bmnsqlite3.vfs_find())
        bmnsqlite3.vfs_register(w3, make_default=1)
        self.assertIs(w3, bmnsqlite3.vfs_find())
        bmnsqlite3.vfs_register(None)
        self.assertIsNone(bmnsqlite3.vfs_find())


@unittest.skipIf(not HAS_CONNECTION_COUNT, "NO connection_count")
class WrapperChangeTestCase(SqlCheckTestCase):

    def test_count(self):
        bmnsqlite3.vfs_register(full.UselessWrapper(), make_default=True)
        c = bmnsqlite3.connect(self.db_path())
        self.assertEqual(bmnsqlite3.connection_count(), 1)
        c1 = bmnsqlite3.connect(self.db_path())
        self.assertEqual(bmnsqlite3.connection_count(), 2)
        c2 = bmnsqlite3.connect(self.db_path())
        self.assertEqual(bmnsqlite3.connection_count(), 3)
        c1.close()
        self.assertEqual(bmnsqlite3.connection_count(), 2)
        c.close()
        self.assertEqual(bmnsqlite3.connection_count(), 1)
        c2.close()
        self.assertEqual(bmnsqlite3.connection_count(), 0)

    def test_reset(self):
        bmnsqlite3.vfs_register(full.UselessWrapper())
        c = bmnsqlite3.connect(self.db_path())
        self.assertEqual(bmnsqlite3.connection_count(), 1)
        c1 = bmnsqlite3.connect(self.db_path())
        self.assertEqual(bmnsqlite3.connection_count(), 2)
        bmnsqlite3.vfs_register(partial.UselessPartialIoWrapper())
        self.assertEqual(bmnsqlite3.connection_count(), 0)
        c = bmnsqlite3.connect(self.db_path("one"))
        self.assertEqual(bmnsqlite3.connection_count(), 1)
        c1 = bmnsqlite3.connect(self.db_path("two"))
        self.assertEqual(bmnsqlite3.connection_count(), 2)
        c2 = bmnsqlite3.connect(self.db_path("three"))
        self.assertEqual(bmnsqlite3.connection_count(), 3)
        c3 = bmnsqlite3.connect(self.db_path("forth"))
        self.assertEqual(bmnsqlite3.connection_count(), 4)
        #
        self._db_write(c2)
        c2.close()
        self.assertEqual(bmnsqlite3.connection_count(), 3)
        c2 = bmnsqlite3.connect(self.db_path("five"))
        self.assertEqual(bmnsqlite3.connection_count(), 4)
        #
        self._db_write(c)
        self._db_write(c1)
        self._db_write(c3)
        c3.close()
        self.assertEqual(bmnsqlite3.connection_count(), 3)

        # the same
        bmnsqlite3.vfs_register(partial.UselessPartialIoWrapper())
        self.assertEqual(bmnsqlite3.connection_count(), 0)


@unittest.skip("TODO:")
class OpenFlagsTestCase(SqlCheckTestCase):

    def test_base(self):
        class OpenFlags(minimal.MinimalFullWrapper):

            def open(self, path: str, flags: int) -> Union[
                    Any, Tuple[Any, int]]:
                return super().open(path, flags), flags

        OpenFlags().test_all(self)

    def test_fail(self):
        class OpenFlags(minimal.MinimalFullWrapper):

            def open(self, path: str, flags: int) -> Union[
                    Any, Tuple[Any, int]]:
                return super().open(path, flags), -1

        self.check_write(OpenFlags(), exception=bmnsqlite3.OperationalError,
                         exception_message="attempt to write a readonly database")


class SectorSizeTestCase(SqlCheckTestCase):

    @unittest.skip("TODO:")
    def test_invalid(self):
        class WrongSize(abstract.XorMixin, crypto.ISectorWrapper , abstract.FillGapRandomMixin):

            def sector_size(self, fh: Any) -> Optional[float]:
                return self.SECTOR_SIZE / 4

        w = WrongSize()

        self.check_write(w, exception=bmnsqlite3.DatabaseError)

    def test_good(self):
        class ValidSize(abstract.XorMixin, abstract.FillGapRandomMixin, crypto.ISectorWrapper):

            def sector_size(self, fh: Any) -> Optional[float]:
                return self.SECTOR_SIZE

        w = ValidSize()

        self.check_write_silent(w)


class WrappersTestCase(unittest.TestCase):
    """
    Test wrappers' implementation without testing BMN features
    Can' be removed on production stage 'cause wrappers itself validated in test
    """

    def test_xor_mixed(self) -> None:
        w = full.XorMixWrapper()
        data = b'9' * 10
        enc_data = w.encrypt(data)
        dec_data = w.decrypt(enc_data)
        self.assertEqual(dec_data, data)
        self.assertTrue(w.validate())


class UriTestCase(SqlCheckTestCase):
    scope = "uri"

    def test_any(self):
        class UriWrapper1(minimal.MinimalFullWrapper):
            pass

        bmnsqlite3.vfs_register(UriWrapper1())
        bmnsqlite3.connect(self.db_path(uri_format=True), uri=True)

        class UriWrapper2(minimal.MinimalFullWrapper):
            
            def full_pathname(self, name: str, out: int) -> Optional[str]:
                if name.startswith("/"):
                    return name[1:]
                return name

        bmnsqlite3.vfs_register(UriWrapper2())
        bmnsqlite3.connect(self.db_path(uri_format=True), uri=True)


class DebugTestCase(unittest.TestCase):
    """
        For debuggin'
    """

    def test_any(self):
        minimal.MinimalPartialWrapper().test_base(self)
