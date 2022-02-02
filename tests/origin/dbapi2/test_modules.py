import sys
from distutils.errors import DistutilsError
from pathlib import Path

import setuptools.config

import bmnsqlite3
from tests.origin import BmnTestCase


class ModuleTests(BmnTestCase):
    def test_dbapi2_exports(self) -> None:
        self.assertEqual("2.0", getattr(bmnsqlite3, "apilevel", None))
        self.assertEqual(1, getattr(bmnsqlite3, "threadsafety", None))
        self.assertEqual("qmark", getattr(bmnsqlite3, "paramstyle", None))

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
            (3,  7): (3, 21, 0),
            (3,  8): (3, 28, 0),
            (3,  9): (3, 32, 3),
            (3, 10): (3, 34, 0),
        }
        python_version = sys.version_info[:2]
        self.assertTrue(python_version in version_map)
        self.assertTrue(
            version_map[python_version],
            bmnsqlite3.sqlite_version_info)

        try:
            setup_config = Path(__file__)
            for _ in range(4):  # stupid
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
