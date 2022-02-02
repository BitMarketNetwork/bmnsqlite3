
import logging
from typing import Any, Tuple, Union, Optional
import os
import unittest
import bmnsqlite3
from tests import SqlCheckTestCase, DbPathMixin, MS_WINDOWS
from tests.wrappers import full, minimal, partial, crypto, abstract

"""
Tests method absence
"""

log = logging.getLogger(__name__)

@unittest.skipIf(not hasattr(bmnsqlite3,"flags") , "Debugging API required for this test")
class FlagsTestCase(SqlCheckTestCase):
    scope = "flags"
    BMN_DEFAULT_VFS = 1 << 0
    BMN_NO_CALLBACK_OPEN = 1 << 1
    BMN_NO_CALLBACK_ACCESS = 1 << 2
    BMN_NO_CALLBACK_DELETE = 1 << 3
    BMN_NO_CALLBACK_RANDOM = 1 << 4
    BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS = 1 << 5
    BMN_NO_CALLBACK_SECTOR_SIZE = 1 << 6
    BMN_NO_CALLBACK_SYNC = 1 << 7
    BMN_NO_CALLBACK_FILE_CONTROL = 1 << 8

    def test_flags_api(self) -> None:
        bmnsqlite3.vfs_register(full.UselessWrapper())
        self.assertEqual(bmnsqlite3.flags(), 0)

    def test_open(self) -> None:
        self.check_connect_silent(partial.UselessPartialIoWrapper())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_OPEN)

    def test_access(self) -> None:
        class NoneAccess(minimal.MinimalFullWrapper):
            pass
        self.check_write_silent(NoneAccess())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_ACCESS)

        class NoAccess(minimal.MinimalFullWrapper):
            def access(self, path: str, flags: int) -> Optional[bool]:
                raise AttributeError("access")

        # delattr(NoAccess,"access")
        self.check_write_silent(NoAccess())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_ACCESS)

    def test_device_characteristics(self) -> None:
        class NoneCharacteristic(minimal.MinimalFullWrapper):
            pass
        self.check_write_silent(NoneCharacteristic())
        self.assertTrue(bmnsqlite3.flags() &
                        self.BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS)

        class NoCharacteristic(minimal.MinimalFullWrapper):
            def device_characteristics(self, fh: Any) -> Optional[int]:
                raise AttributeError("device_characteristics")

        self.check_write_silent(NoCharacteristic())
        self.assertTrue(bmnsqlite3.flags() &
                        self.BMN_NO_CALLBACK_DEVICE_CHARACTERISTICS)

    def test_sector_size(self) -> None:
        class NoneSectorSize(minimal.MinimalFullWrapper):
            pass
        self.check_write_silent(NoneSectorSize())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_SECTOR_SIZE)

        class NoSectorSize(minimal.MinimalFullWrapper):
            def sector_size(self, fh: Any) -> Optional[float]:
                raise AttributeError("sector_size")

        self.check_write_silent(NoSectorSize())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_SECTOR_SIZE)

    def test_sync(self) -> None:
        # sync returns nothing so BMN has no chance to know wether method implemented or not
        # class NoneSync(minimal.MinimalFullWrapper):
        #     pass
        # self.check_write_silent(NoneSync())
        # self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_SYNC)

        class NoSync(minimal.MinimalFullWrapper):
            def sync(self, fh: Any, flags: int) -> None:
                raise AttributeError("sync")

        self.check_write_silent(NoSync())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_SYNC)

    def test_file_control(self) -> None:
        class NoneFileControl(minimal.MinimalFullWrapper):
            pass
        self.check_vacuum_silent(NoneFileControl())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_FILE_CONTROL)

        class NoFileControl(minimal.MinimalFullWrapper):
            def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
                raise AttributeError("file_control")

        self.check_vacuum_silent(NoFileControl())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_FILE_CONTROL)

    @unittest.skip("TODO")
    def test_random_none(self) -> None:

        class NoneRandom(abstract.IDeleteMixin, minimal.MinimalFullWrapper):
            pass

        self.check_random_silent(NoneRandom())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_RANDOM)

    @unittest.skip("TODO")
    def test_random(self) -> None:
        
        class NoRandom(abstract.IDeleteMixin, minimal.MinimalFullWrapper):

            def random(self, size: int) -> Optional[bytes]:
                raise AttributeError("random")

        self.check_random_silent(NoRandom())
        self.assertTrue(bmnsqlite3.flags() & self.BMN_NO_CALLBACK_RANDOM)
