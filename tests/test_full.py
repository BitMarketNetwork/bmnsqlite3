from tests.wrappers import full, crypto, minimal
import bmnsqlite3
import logging
import unittest
import time
from typing import Any, Optional

log = logging.getLogger(__name__)


class FullTestCase(unittest.TestCase):

    def test_useless(self):
        full.UselessWrapper().test_base(self)

    def test_base64(self):
        full.Base64Wrapper().test_base(self)

    def test_xor(self):
        full.XorWrapper().test_all(self)

    def test_xor_mix(self):
        full.XorMixWrapper().test_all(self)

    def test_zip(self):
        crypto.ZipWrapper().test_all(self)
        crypto.ZipMessyWrapper().test_all(self, skip_vacuum=True)

    def test_sleep(self):
        # eats too much time
        full.SleepWrapper().test_all(self, skip_heavy=True)

    def test_aes_cfb(self):
        crypto.AesCfbWrapper().test_all(self)

    def test_aes_ecb(self):
        crypto.AesEcbWrapper().test_all(self)

    def test_fernet(self):
        crypto.FernetWrapper().test_all(self)

    def test_fernet_persistent(self):
        # two times intentionally to test persistence
        # avoid launching all tests to save time
        crypto.PersistentFernetIoWrapper().test_readwrite(self)
        crypto.PersistentFernetIoWrapper().test_readwrite(self)


class IterDumpTestCase(unittest.TestCase):

    def test_useless(self):
        full.UselessWrapper().test_iterdump(self)


class VacuumTestCase(unittest.TestCase):

    def test_vacuum_works(self):
        full.XorWrapper().test_vacuum(self)
        full.Base64Wrapper().test_vacuum(self)
        crypto.ZipWrapper().test_vacuum(self)
        crypto.FernetWrapper().test_vacuum(self)

    def test_vacuum_refused(self):
        zw = crypto.ZipMessyWrapper()
        with self.assertWarnsRegex(bmnsqlite3.WrapperWarning, "ZipMessyWrapper"):
            with self.assertRaises(bmnsqlite3.ProgrammingError) as pe:
                zw.test_vacuum(self)

    def test_time(self):
        start = time.time()
        crypto.ZipWrapper().test_vacuum(self)
        zeros_duration = time.time() - start
        start = time.time()
        crypto.ZipFastWrapper().test_vacuum(self)
        fast_zeros_duration = time.time() - start
        # no profit ?? 
        # self.assertGreater(zeros_duration,fast_zeros_duration )
