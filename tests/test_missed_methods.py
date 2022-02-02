import unittest
from typing import Union

import bmnsqlite3
from tests import UNRAISABLE_ARGS_TYPE, SqlCheckTestCase
from tests.wrappers import abstract, minimal


class OpenCloseTestCase(SqlCheckTestCase):

    def test_no_close(self):
        class NoClose(abstract.IOpenMixin):
            """
            If wrapper has 'open' then it got to have 'close'!
            """

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, NameError)
            self.assertIn("close", str(args.exc_value))
            self.assertIn("mandatory", str(args.exc_value))

        w = NoClose()
        self.check_connect(w, error_hook)

    def test_no_encode_decode(self):
        class NoEncode:
            """
            If wrapper has no 'open' then it has
                got to have 'encode' and 'decode'!
            """

            def decode(self, file_flags: int, callback: callable,
                       length: int, offset: int) -> Union[bytes, bool]:
                return callback(length, offset)

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, NameError)
            self.assertIn("encode", str(args.exc_value))
            self.assertIn("mandatory", str(args.exc_value))

        w = NoEncode()
        self.check_write(w, error_hook)

        class NoDecode:
            """
            If wrapper has no 'open' then it got to have 'encode' and 'decode'!
            """

            def encode(self, file_flags: int, callback: callable, data: bytes,
                       offset: int) -> None:
                callback(data, offset)

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, NameError)
            self.assertIn("decode", str(args.exc_value))
            self.assertIn("mandatory", str(args.exc_value))

        w = NoDecode()
        self.check_connect(w, error_hook)


class MinimalImplTestCase(unittest.TestCase):

    def test_full(self):
        minimal.MinimalFullWrapper().test_all(self)

    def test_partial(self):
        minimal.MinimalPartialWrapper().test_all(self)
