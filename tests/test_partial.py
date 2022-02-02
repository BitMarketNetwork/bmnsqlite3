import unittest

from tests.wrappers import partial


class PartialBindingTestCase(unittest.TestCase):

    def test_useless(self):
        """this wrapper does nothing but shows
        how to implement partial binding"""
        partial.UselessPartialIoWrapper().test_all(self)

    def test_xor(self):
        partial.XorPartialIoWrapper().test_all(self)

    def test_zip(self):
        partial.ZipPartialWrapper().test_all(self)

    def test_aes_cfb(self):
        partial.AesCfbPartialWrapper().test_all(self)

    def test_aes_ecb(self):
        partial.AesEcbPartialWrapper().test_all(self)

    def test_fernet(self):
        partial.FernetPartialWrapper().test_all(self)
