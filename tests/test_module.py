import sys
import time
from distutils.errors import DistutilsError
from pathlib import Path

import setuptools.config

import bmnsqlite3
from unittest import TestCase


class TestModule(TestCase):
    def test_dbapi2_globals(self) -> None:
        self.assertEqual("2.0", getattr(bmnsqlite3, "apilevel", None))
        self.assertEqual(1, getattr(bmnsqlite3, "threadsafety", None))
        self.assertEqual("qmark", getattr(bmnsqlite3, "paramstyle", None))

    def test_dbapi2_date_time(self) -> None:
        ticks = 7 * 24 * 60 * 60 - 2
        if not time.localtime().tm_isdst:
            ticks += time.timezone
        else:
            ticks += time.altzone

        self.assertEqual(1970, bmnsqlite3.DateFromTicks(ticks).year)
        self.assertEqual(1, bmnsqlite3.DateFromTicks(ticks).month)
        self.assertEqual(7, bmnsqlite3.DateFromTicks(ticks).day)
        self.assertEqual(23, bmnsqlite3.TimeFromTicks(ticks).hour)
        self.assertEqual(59, bmnsqlite3.TimeFromTicks(ticks).minute)
        self.assertEqual(58, bmnsqlite3.TimeFromTicks(ticks).second)
        self.assertEqual(0, bmnsqlite3.TimeFromTicks(ticks).microsecond)

        self.assertEqual(1970, bmnsqlite3.TimestampFromTicks(ticks).year)
        self.assertEqual(1, bmnsqlite3.TimestampFromTicks(ticks).month)
        self.assertEqual(7, bmnsqlite3.TimestampFromTicks(ticks).day)
        self.assertEqual(23, bmnsqlite3.TimestampFromTicks(ticks).hour)
        self.assertEqual(59, bmnsqlite3.TimestampFromTicks(ticks).minute)
        self.assertEqual(58, bmnsqlite3.TimestampFromTicks(ticks).second)
        self.assertEqual(0, bmnsqlite3.TimestampFromTicks(ticks).microsecond)

        self.assertTrue(hasattr(bmnsqlite3, "Binary"))
        self.assertTrue(hasattr(bmnsqlite3, "STRING"))
        self.assertTrue(hasattr(bmnsqlite3, "BINARY"))
        self.assertTrue(hasattr(bmnsqlite3, "NUMBER"))
        self.assertTrue(hasattr(bmnsqlite3, "DATETIME"))
        self.assertTrue(hasattr(bmnsqlite3, "ROWID"))

    def test_dbapi2_exceptions(self) -> None:
        self.assertTrue(issubclass(bmnsqlite3.Warning, Exception))
        self.assertTrue(issubclass(bmnsqlite3.Error, Exception))

        if True:
            self.assertTrue(issubclass(
                bmnsqlite3.InterfaceError,
                bmnsqlite3.Error))
            self.assertTrue(issubclass(
                bmnsqlite3.DatabaseError,
                bmnsqlite3.Error))

            if True:
                self.assertTrue(issubclass(
                    bmnsqlite3.DataError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.OperationalError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.IntegrityError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.InternalError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.ProgrammingError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.NotSupportedError,
                    bmnsqlite3.DatabaseError))
                self.assertTrue(issubclass(
                    bmnsqlite3.WrapperError,
                    bmnsqlite3.DatabaseError))

    def test_version(self) -> None:
        self.assertTrue(hasattr(bmnsqlite3, "version_info"))
        self.assertTrue(hasattr(bmnsqlite3, "sqlite_version_info"))

        # sync with README.md / 3rdparty
        version_map = {
            # python_version: sqlite_version
            (3, 7): (3, 37, 2),
            (3, 8): (3, 37, 2),
            (3, 9): (3, 37, 2),
            (3, 10): (3, 37, 2),
        }
        python_version = sys.version_info[:2]
        self.assertTrue(python_version in version_map)
        self.assertTrue(
            version_map[python_version],
            bmnsqlite3.sqlite_version_info)

        try:
            setup_config = Path(__file__)
            for _ in range(2):
                setup_config = setup_config.parent
                self.assertTrue(setup_config.exists())
            setup_config /= "setup.cfg"
            self.assertTrue(setup_config.exists())
            setup_config = setuptools.config.read_configuration(setup_config)
        except DistutilsError as e:
            self.fail(str(e))
        self.assertTrue("metadata" in setup_config)
        self.assertTrue("version" in setup_config["metadata"])
        version = tuple(
            int(x) for x in setup_config["metadata"]["version"].split("."))
        self.assertEqual(3, len(version))
        self.assertEqual(version, bmnsqlite3.version_info)
