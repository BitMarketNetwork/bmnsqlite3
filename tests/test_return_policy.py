import unittest
import logging
from typing import Any, Type, Union, Optional

import bmnsqlite3
from tests import UNRAISABLE_ARGS_TYPE, SqlCheckTestCase
from tests.wrappers import full, partial
from tests.wrappers.partial import ENCODE_CALLBACK_SIGNATURE, DECODE_CALLBACK_SIGNATURE

"""
Testing values returned by wrapper's methods
"""

log = logging.getLogger(__name__)


class ReturnPolicyTestCase(SqlCheckTestCase):
    scope = "return_policy"

    def test_open(self):
        class ReturnBool:
            def open(self, *_):
                return False

        class ReturnNumber:
            def open(self, *_):
                return 3.14

        w = ReturnBool()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("open", str(args.exc_value))

        self.check_connect(
            w, error_hook, exception=bmnsqlite3.OperationalError)
        w = ReturnNumber()
        self.check_connect(
            w, error_hook, exception=bmnsqlite3.OperationalError)

        class ReturnNone:
            """
            it is not normal when 'open' returns None, because if we implemented
            this method, so we took responsibility for DB control

            nevertheless if we want to use partial implementation and don't take
            responsibility for DB _we mustn't implement 'open' method at all_
            and let sqlite to do the work
            """

            def open(self, *_):
                return None

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            error_hook(args)
            self.assertIn("None", str(args.exc_value))

        w = ReturnNone()
        self.check_connect(
            w, error_hook_, exception=bmnsqlite3.OperationalError)

    def test_write(self):
        class ReturnAny(full.UselessWrapper):

            # noinspection PyTypeChecker
            def write(self, fh: Any, data: bytes, offset: int) -> int:
                # noinspection PyTypeChecker
                super().write(fh, data, offset)
                return {}

        self.check_write_warns(ReturnAny(), regex="ignored")

    def test_read(self):
        class ReturnNotBytes(full.UselessWrapper):

            def read(self, fh: Any, length: int, offset: int) -> bytes:
                # noinspection PyTypeChecker
                return 9

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("read", str(args.exc_value))

        w = ReturnNotBytes()
        self.check_connect(w, error_hook)

        class ReturnNone(full.UselessWrapper):
            """
            'read' is necessary and important method so None is not valid result
            """

            def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
                pass

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            error_hook(args)
            self.assertIn("None", str(args.exc_value))

        w = ReturnNone()
        self.check_connect(w, error_hook_)

        class ReturnBool(full.UselessWrapper):
            """
            BMN library treats it as valid implementation, but sqlite can't read anything from file in
            this case and raises DatabaseError
            """

            def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
                return True

        w = ReturnBool()
        self.check_write(w, None, exception=bmnsqlite3.DatabaseError,
                         exception_message='file is not a database')

        class ReturnWrongSize(full.UselessWrapper):
            """
            Method should return exactly 'length' bytes or bool if it isn't possible
            """

            def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
                return b'0' * length * 2

        def error_hook__(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, ValueError)
            self.assertIn("read", str(args.exc_value))
            self.assertIn("wrong number of bytes", str(args.exc_value))

        w = ReturnWrongSize()
        self.check_connect(w, error_hook__)

    def test_access(self):
        class ReturnNone(full.UselessWrapper):
            """
            'access' doesn't take file handle so sqlite can work without this method
            """

            def access(self, path: str, flags: int) -> Optional[bool]:
                return None

        # not an error
        self.check_write_silent(ReturnNone())

        class ReturnNumber(full.UselessWrapper):
            """
            but user must stick to the api
            this is an error
            """

            def access(self, path: str, flags: int) -> Optional[bool]:
                # noinspection PyTypeChecker
                return 90.1

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("access", str(args.exc_value))

        w = ReturnNumber()
        self.check_write(w, error_hook)

        class ReturnDict(full.UselessWrapper):

            def access(self, path: str, flags: int) -> Optional[bool]:
                # noinspection PyTypeChecker
                return {}

        w = ReturnDict()
        self.check_write(w, error_hook)

    def test_encode(self):
        """
        Partial method
        """

        class ReturnNone(partial.UselessPartialIoWrapper):
            """
            BMN library treats it as valid implementation, but sqlite raises another errors,
            because we don't write anything
            """

            def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> None:
                pass

        # TODO: what's wrong with it? Seems like gives different results
        # self.check_write(ReturnNone(), exception=bmnsqlite3.OperationalError)

        class ReturnAny(partial.UselessPartialIoWrapper):
            """
            Encode don't need to return anything, if it did it - it isn't an error but BMN emits warning
            """

            # noinspection PyTypeChecker
            def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> None:
                super().encode(file_flags, callback, data, offset)
                return {}

        self.check_write_warns(ReturnAny(), regex=r"ignored")

    def test_decode(self):
        """
        Partial method
        """

        class ReturnNone(partial.UselessPartialIoWrapper):
            """
            The same as in test_read 'ReturnNone'
            """

            def decode(self, file_flags: int, callback: DECODE_CALLBACK_SIGNATURE, length: int, offset: int) -> Union[
                    bytes, bool]:
                pass

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("decode", str(args.exc_value))

        w = ReturnNone()
        self.check_connect(w, error_hook)

        class ReturnBool(partial.UselessPartialIoWrapper):
            """
            The same as in test_read 'ReturnBool'
            """

            def decode(self, file_flags: int, callback: DECODE_CALLBACK_SIGNATURE, length: int, offset: int) -> Union[
                    bytes, bool]:
                return True

        w = ReturnBool()
        self.check_write(w, None, exception=bmnsqlite3.DatabaseError,
                         exception_message='file is not a database')

        class ReturnWrongSize(partial.UselessPartialIoWrapper):
            """
            The same as in test_read 'ReturnWrongSize'
            """

            def decode(self, file_flags: int, callback: DECODE_CALLBACK_SIGNATURE, length: int, offset: int) -> Union[
                    bytes, bool]:
                return callback(length * 2, offset)

        def error_hook__(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, ValueError)
            self.assertIn("decode", str(args.exc_value))
            self.assertIn("wrong number of bytes", str(args.exc_value))

        w = ReturnWrongSize()
        self.check_connect(w, error_hook__)

    def test_close(self):
        class ReturnAny(full.UselessWrapper):
            """
            BMN doesn't require any result from close
            """

            def close(self, fh: Any) -> None:
                super().close(fh)
                # noinspection PyTypeChecker
                return 1,

        self.check_connect_warns(ReturnAny(), regex=r"ignored")

    def test_delete(self):
        class ReturnAny(full.UselessWrapper):
            """
            BMN doesn't require any result from delete
            """

            def delete(self, path: str, sync_dir: bool) -> None:
                super().delete(path, sync_dir)
                # noinspection PyTypeChecker
                return False

        self.check_write_warns(ReturnAny(), regex=r"ignored")

    def test_truncate(self):
        """
        This is valid test, but need to find ways to make sqlite truncate file
        """

        class ReturnAny(full.UselessWrapper):
            """
            BMN doesn't require any result from truncate
            """

            def truncate(self, fh: Any, size: int) -> None:
                super().truncate(fh, size)
                # noinspection PyTypeChecker
                return []

        w = ReturnAny()
        self.check_vacuum_warns(ReturnAny(), regex=r"ignored")

    def test_file_control(self):
        class ReturnNone(full.UselessWrapper):
            """
            None is normal because fil_control optional stuff
            """

            def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
                return None

        w = ReturnNone()
        self.check_vacuum_silent(w)

        class ReturnWrongType(full.UselessWrapper):
            """
            Only bool expected
            """

            def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
                # be carefull
                if 11 == operation:
                    # noinspection PyTypeChecker
                    return {}

        w = ReturnWrongType()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("file_control", str(args.exc_value))
            
        self.check_vacuum(w, error_hook)

    def test_file_size(self):
        class ReturnNone(full.UselessWrapper):
            """
            Only int expected
            """

            def file_size(self, fh: Any) -> int:
                # noinspection PyTypeChecker
                return None

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, NameError)
            self.assertIn("file_size", str(args.exc_value))

        w = ReturnNone()
        self.check_write(w, error_hook)

        class ReturnWrongType(full.UselessWrapper):
            """
            Only int expected
            """

            def file_size(self, fh: Any) -> int:
                # noinspection PyTypeChecker
                return {}

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("file_size", str(args.exc_value))


        w = ReturnWrongType()
        self.check_write(w, error_hook)

    @unittest.skip("TODO")
    def test_random(self):
        """
        This is valid test, but need to find ways to make sqlite truncate file
        """

        class ReturnInt(full.UselessWrapper):
            """
            Only bytes expected
            """

            def random(self, size: int) -> Optional[bytes]:
                # noinspection PyTypeChecker
                return size

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, bmnsqlite3.WrapperError)
            self.assertIn("random", str(args.exc_value))

        w = ReturnInt()
        self.check_write_silent(w, error_hook)

        class ReturnNone(full.UselessWrapper):
            """
            Only bytes expected but this method is optional
            """

            def random(self, size: int) -> Optional[bytes]:
                # noinspection PyTypeChecker
                return None

        self.resetHookCall()
        # self.check_write_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnUnderflow(full.UselessWrapper):
            """
            Only bytes expected but this method is optional
            """

            def random(self, size: int) -> Optional[bytes]:
                return b'0' * (size - 1)

        w = ReturnUnderflow()
        self.check_write_silent(w, error_hook)

        class ReturnOverflow(full.UselessWrapper):
            """
            Only bytes expected but this method is optional
            """

            def random(self, size: int) -> Optional[bytes]:
                return b'0' * size * 2

        w = ReturnOverflow()
        self.check_write_silent(w, error_hook)

    def test_device_characterstics(self):
        class ReturnNone(full.UselessWrapper):
            """
            Not an error .. just do default action
            """

            def device_characteristics(self, fh: Any) -> Optional[int]:
                # noinspection PyTypeChecker
                return None

        w = ReturnNone()

        self.check_connect_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnOutOfRange(full.UselessWrapper):

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return int(1e20)

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, OverflowError)
            self.assertIs(args.object, w)
            self.assertIn("device_characteristics", str(args.exc_value))
            self.assertIn("out of range", str(args.exc_value))

        w = ReturnOutOfRange()
        self.check_connect_silent(w, error_hook_)

        class ReturnNegative(full.UselessWrapper):

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return -1

        w = ReturnNegative()
        self.check_connect_silent(w, error_hook_)

    def test_sector_size(self):
        class ReturnNone(full.UselessWrapper):
            """
            Not an error .. just do default action
            """

            def sector_size(self, fh: Any) -> Optional[float]:
                # noinspection PyTypeChecker
                return None

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0

        self.check_write_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnOutOfRangeLongLong(ReturnNone):

            def sector_size(self, fh: Any) -> Optional[float]:
                return int(1e20)

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, OverflowError)
            self.assertIs(args.object, w)
            self.assertIn("sector_size", str(args.exc_value))
            self.assertIn("out of range", str(args.exc_value))

        w = ReturnOutOfRangeLongLong()
        self.check_write_silent(w, error_hook_)

        class ReturnOutOfRangeDouble(ReturnNone):

            def sector_size(self, fh: Any) -> Optional[float]:
                return 1e20

        w = ReturnOutOfRangeDouble()
        self.check_write_silent(w, error_hook_)

        class ReturnNegative(ReturnNone):

            def sector_size(self, fh: Any) -> Optional[float]:
                return -1

        w = ReturnNegative()
        self.check_write_silent(w, error_hook_)

    def test_sector_size_tweak(self):
        _4096 = 4096

        class Return4096(full.UselessWrapper):

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0

        self.erase_db()
        self.check_write_silent(Return4096())
        self.assertUnraisableNotCalled()

        # self.assertEqual(self.db_size(), _4096 * 2)

        class Return8192(Return4096):

            def sector_size(self, fh: Any) -> Optional[float]:
                return _4096 * 2

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0

        self.erase_db()
        self.check_write_silent(Return8192())
        self.assertUnraisableNotCalled()
        self.assertEqual(self.db_size(), _4096 * 4)

        class Return2048float(Return4096):
            """
            also tests floats !
            """

            def sector_size(self, fh: Any) -> Optional[float]:
                return _4096 * 4.

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0

        self.erase_db()
        self.check_write_silent(Return2048float())
        self.assertUnraisableNotCalled()
        self.assertEqual(self.db_size(), _4096 * 4)

    def test_full_pathname(self):
        class ReturnNone(full.UselessWrapper):
            """
            BMN silence this case. No warnings or errors.
            Just returning name as a result
            """

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                # noinspection PyTypeChecker
                return None

        w = ReturnNone()
        self.check_connect_silent(w)
        self.assertUnraisableNotCalled()

    def test_full_pathname_unicode(self) -> None:
        class WideUnicode(full.UselessWrapper):

            # noinspection PyMethodParameters
            def full_pathname(self_, name: str, out: int) -> Optional[str]:
                return self.db_path("кириллица")

        self.resetHookCall()
        w = WideUnicode()
        self.check_write_silent(w)
        self.assertUnraisableNotCalled()

        class WideWideUnicode(full.UselessWrapper):

            # noinspection PyMethodParameters
            def full_pathname(self_, name: str, out: int) -> Optional[str]:
                return self.db_path("🅘🅝🅓🅘🅥🅘🅓🅤🅐🅛🅘🅣🅨")

        w = WideWideUnicode()
        self.resetHookCall()
        self.check_write_silent(w)
        self.assertUnraisableNotCalled()

        class ComplexUnicode(full.UselessWrapper):

            # noinspection PyMethodParameters
            def full_pathname(self_, name: str, out: int) -> Optional[str]:
                return self.db_path("\u0043\u0327")

        w = ComplexUnicode()
        self.resetHookCall()
        self.check_write_silent(w)
        self.assertUnraisableNotCalled()

        class BufferOverflow(full.UselessWrapper):

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                return "a" * (out + 1)

        w = BufferOverflow()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, OverflowError)
            self.assertIs(args.object, w)
            self.assertIn("full_pathname", str(args.exc_value))
            self.assertIn("longer than", str(args.exc_value))

        self.check_connect(
            w, error_hook, exception=bmnsqlite3.OperationalError)

        class ExactLength(full.UselessWrapper):

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                return "a" * out

        self.resetHookCall()
        self.check_connect(
            ExactLength(), exception=bmnsqlite3.OperationalError)
        self.assertUnraisableNotCalled()

        class ReturnWrong(full.UselessWrapper):
            """
            But this is an error
            """

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                # noinspection PyTypeChecker
                return 90

        w = ReturnWrong()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("full_pathname", str(args.exc_value))

        self.check_connect(w, error_hook)

    def test_full_pathname_unicode_valid_tweak(self) -> None:
        db_path: str = ""

        class MoreChecks(full.UselessWrapper):

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                nonlocal db_path
                db_path = name + "_больше_🅘🅝🅓🅘🅥🅘🅓🅤🅐🅛🅘🅣.db"
                return db_path

        w = MoreChecks()
        self.resetHookCall()
        self.check_write_silent(w)
        self.assertUnraisableNotCalled()
        self.assertGreaterEqual(self.db_size(db_path), 8192)

    def test_current_time(self) -> None:
        class ReturnNone(full.UselessWrapper):

            # set iVersion to 1 to test
            def current_time(self) -> float:
                pass

            def current_time_int64(self) -> int:
                pass

        self.check_write_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnAny(full.UselessWrapper):

            # set iVersion to 1 to test
            def current_time(self) -> float:
                return {}

            def current_time_int64(self) -> int:
                # noinspection PyTypeChecker
                return {}

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.object, w)
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("current_time", str(args.exc_value))

        w = ReturnAny()
        self.check_write_silent(w, error_hook)

    def test_sync(self) -> None:
        class ReturnNone(full.UselessWrapper):

            def sync(self, fh: Any, flags: int) -> None:
                pass

        self.check_write_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnAny(full.UselessWrapper):

            def sync(self, fh: Any, flags: int) -> None:
                # noinspection PyTypeChecker
                return {}

        self.check_write_warns(ReturnAny())

    def test_sleep(self) -> None:
        class ReturnNone(full.UselessWrapper):

            def sleep(self, microseconds: int) -> Optional[int]:
                return super().sleep(microseconds)

        self.check_write_silent(ReturnNone())
        self.assertUnraisableNotCalled()

        class ReturnAny(full.UselessWrapper):

            def sync(self, fh: Any, flags: int) -> None:
                # noinspection PyTypeChecker
                return {}

        self.check_write_warns(ReturnAny())
