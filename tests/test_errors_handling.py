import sys
import unittest
import logging
from typing import Any, Optional, Union, Callable

import bmnsqlite3
from tests import MS_WINDOWS, SqlCheckTestCase, TracebackHelper, UNRAISABLE_ARGS_TYPE
from tests.wrappers import partial, full
from tests.wrappers.partial import DECODE_CALLBACK_SIGNATURE, ENCODE_CALLBACK_SIGNATURE

log = logging.getLogger(__name__)


class ErrorsHandlingTestCase(SqlCheckTestCase):
    scope = "errors_handling"

    def setUp(self) -> None:
        super().setUp()
        self.erase_db()

    def tearDown(self) -> None:
        super().tearDown()
        self.erase_db()

    @unittest.skipIf(not MS_WINDOWS, "TODO check it on unix")
    def test_bad_uri_parameter(self) -> None:
        bmnsqlite3.vfs_register(full.UselessWrapper(), make_default=True)
        with self.assertRaises(bmnsqlite3.OperationalError):
            with bmnsqlite3.connect("%s?fail=fail" % self.db_path(), uri=True) as c:
                pass

    def test_open_miss(self) -> None:
        """to ensure that absence of 'open' doesn't throw anything"""

        class SkipOpen(partial.UselessPartialIoWrapper):
            pass

        bmnsqlite3.vfs_register(SkipOpen())
        bmnsqlite3.connect(self.db_path())
        self.assertUnraisableNotCalled()

    def test_full_pathname_miss(self) -> None:
        """to ensure that absence of 'full_pathname' doesn't throw anything"""

        class SkipFullPathname(full.UselessWrapper):

            def full_pathname(self, name: str, out: int) -> str:
                raise RuntimeError()

        delattr(full.ISimpleWrapper, "full_pathname")
        delattr(SkipFullPathname, "full_pathname")

        bmnsqlite3.vfs_register(SkipFullPathname())
        bmnsqlite3.connect(self.db_path())
        self.assertUnraisableNotCalled()

    def test_open_raise_exception(self) -> None:
        class OpenException:
            def open(self, path: str, flags: int) -> Any:
                raise RuntimeError("fail")

        w = OpenException()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertEqual(str(args.exc_value), "fail")
            # self.assertEqual(args.err_msg, "fail")
            self.assertIs(args.object, w)

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "open")

    def test_open_failure(self) -> None:
        class OpenError:
            def open(self, path: str, flags: int) -> Any:
                path /= flags

        w = OpenError()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, TypeError)
            self.assertIn("unsupported operand", str(args.exc_value))
            self.assertIs(args.object, w)

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "open")

    def test_open_failures_chain(self) -> None:
        class OpenFailureChain:
            def some_method2(self) -> float:
                return 1 / 0

            def some_method1(self, _) -> float:
                return self.some_method2()

            def open(self, fh: Any, _) -> Any:
                self.some_method1(fh)

        w = OpenFailureChain()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, ZeroDivisionError)
            self.assertIs(args.object, w)
            tb = TracebackHelper.from_hook(args)
            callstack = [
                "open",
                "some_method1",
                "some_method2",
            ]
            for i, t in enumerate(tb):
                self.assertEqual(str(t), callstack[i], i)

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "open")

    def test_close_failure(self) -> None:
        class CloseFailure(full.UselessWrapper):

            def close(self, fh: Any) -> None:
                # we should close file anyway avoiding resource warnings
                super().close(fh)
                raise RuntimeError("close")

        w = CloseFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "close")

        self.check_connect_silent(w, error_hook)
        self.assertExceptionLocation(w, "close")

    def test_read_failure(self) -> None:
        class ReadFailure(full.UselessWrapper):

            def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
                raise RuntimeError("read")

        w = ReadFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "read")

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "read")

    def test_read_wrong_bytes_count(self) -> None:
        class ReadWrongBytesCount(full.UselessWrapper):
            """
            Read should return strictly 'length' bytes
            """

            def read(self, fh: Any, length: int, offset: int) -> bytes:
                return b'0' * length * 2

        w = ReadWrongBytesCount()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, ValueError)
            self.assertIs(args.object, w)
            self.assertIn("read", str(args.exc_value))
            self.assertIn("wrong number of bytes", str(args.exc_value))

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "read")

    def test_write_failure(self) -> None:
        class WriteFailure(full.UselessWrapper):

            def write(self, fh: Any, data: bytes, offset: int) -> int:
                raise RuntimeError("write")

        w = WriteFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "write")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "write")

    def test_access_failure(self) -> None:
        class AccessFailure(full.UselessWrapper):

            def access(self, path: str, flags: int) -> Optional[bool]:
                raise RuntimeError("access")

        w = AccessFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "access")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "access")

    def test_file_size_failure(self) -> None:

        class FileSizeFailure(full.UselessWrapper):

            def file_size(self, fh: Any) -> int:
                raise RuntimeError("file_size")

        w = FileSizeFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "file_size")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "file_size")

    def test_sector_size_failure(self) -> None:
        class SectorSizeFailure(full.UselessWrapper):

            def sector_size(self, fh: Any) -> Optional[float]:
                raise RuntimeError("sector_size")

            def device_characteristics(self, fh: Any) -> Optional[int]:
                return 0

        w = SectorSizeFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "sector_size")

        self.check_write_silent(w, error_hook)

    def test_device_characteristics_failure(self) -> None:
        class DeviceCharacteristicsFailure(full.UselessWrapper):

            def device_characteristics(self, fh: Any) -> Optional[int]:
                raise RuntimeError("device_characteristics")

        w = DeviceCharacteristicsFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "device_characteristics")

        self.check_connect_silent(w, error_hook)

    def test_full_pathname_failure(self) -> None:
        class FullPathnameFailure(full.UselessWrapper):

            def full_pathname(self, name: str, out: int) -> Optional[str]:
                raise RuntimeError("full_pathname")

        w = FullPathnameFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "full_pathname")

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "full_pathname")

    @unittest.skip("TODO")
    def test_random_failure(self) -> None:
        # it works when one test is launched but doesn't in the whole testcase set

        class RandomFailure(full.UselessWrapper):

            def random(self, size: int) -> Optional[bytes]:
                raise RuntimeError("random")

        w = RandomFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "random")

        self.check_write_silent(w, error_hook)
        self.assertExceptionLocation(w, "random")

    def test_delete_failure(self) -> None:

        class DeleteFailure(full.UselessWrapper):

            def delete(self, path: str, sync_dir: bool) -> None:
                raise RuntimeError("delete")

        w = DeleteFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "delete")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "delete")

    def test_truncate_failure(self) -> None:
        class TruncateFailure(full.UselessWrapper):

            def truncate(self, fh: Any, size: int) -> int:
                raise RuntimeError("truncate")

        w = TruncateFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "truncate")

        self.check_vacuum(w, error_hook)
        self.assertExceptionLocation(w, "truncate")

    def test_file_control_failure(self) -> None:
        class FileControlFailure(full.UselessWrapper):

            def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
                raise RuntimeError("file_control")

        w = FileControlFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "file_control")
            # tb = TracebackHelper.from_hook(args)
            # for t in tb:
            #     log.warning(">> %s" , t)

        self.check_vacuum(w, error_hook)
        self.assertExceptionLocation(w, "file_control")

    def test_sync_failure(self) -> None:

        class SyncFailure(full.UselessWrapper):

            def sync(self, fh: Any, flags: int) -> None:
                raise RuntimeError("sync")

        w = SyncFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "sync")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "sync")

    def test_current_time_failure(self) -> None:

        class CurrentTimeFailure(full.UselessWrapper):

            # set iVersion to 1 to test
            def current_time(self) -> float:
                raise RuntimeError("current_time")

            def current_time_int64(self) -> int:
                raise RuntimeError("current_time_int64")

        w = CurrentTimeFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertIn("current_time", str(args.exc_value))

        self.check_write_silent(w, error_hook)

    @unittest.skip("TODO")
    def test_sleep_failure(self) -> None:

        class SleepFailure(full.UselessWrapper):

            def sleep(self, microseconds: int) -> Optional[int]:
                raise RuntimeError("sleep")

        w = SleepFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "sleep")

        sys.unraisablehook = self.discover_exception(error_hook)
        table_name = "cwcwcw"
        bmnsqlite3.vfs_register(w)
        with bmnsqlite3.connect(self.db_path()) as source:
            c = source.cursor()
            query = f"CREATE TABLE IF NOT EXISTS {table_name}(title text)"
            c.execute(query)
            c.execute(f"INSERT INTO {table_name} VALUES (?)", ("cwcw",))
            c.close()
            with bmnsqlite3.connect(self.db_path("next")) as target:
                source.backup(target, pages=1)


class PartialErrorsTestCase(SqlCheckTestCase):

    def test_partial_decode(self) -> None:
        class DecodeFailure(partial.UselessPartialIoWrapper):

            def decode(self, file_flags: int, callback, length: int, offset: int) -> Optional[bytes]:
                raise RuntimeError("decode")

        w = DecodeFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "decode")

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "decode")

    def test_decode_wrong_bytes_count(self) -> None:
        class DecodeWrongBytesCount(partial.UselessPartialIoWrapper):
            """
            Read should return strictly 'length' bytes
            """

            def decode(self, file_flags: int, callback: DECODE_CALLBACK_SIGNATURE, length: int, offset: int) -> Union[
                    bytes, bool]:
                return b'0' * length * 2

        w = DecodeWrongBytesCount()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, ValueError)
            self.assertIs(args.object, w)
            self.assertIn("decode", str(args.exc_value))
            self.assertIn("wrong number of bytes", str(args.exc_value))

        self.check_connect(w, error_hook)
        self.assertExceptionLocation(w, "decode")

    def test_partial_encode(self) -> None:
        class EncodeFailure(partial.UselessPartialIoWrapper):

            def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> int:
                raise RuntimeError("encode")

        w = EncodeFailure()

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertEqual(args.exc_type, RuntimeError)
            self.assertIs(args.object, w)
            self.assertEqual(str(args.exc_value), "encode")

        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "encode")

    def test_encode_callback_failure(self):
        class EncodeCallbackFailure(partial.UselessPartialIoWrapper):

            def encode(self, file_flags: int, callback: Callable[[bytes, int], None],
                       data: bytes, offset: int) -> None:
                callback(data, -1)

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.exc_type, ValueError)
            self.assertIs(args.object, w)
            self.assertIn("encode", str(args.exc_value), )

        w = EncodeCallbackFailure()
        self.check_write(w, error_hook)

        class EncodeCallbackTypeFailure(partial.UselessPartialIoWrapper):

            def encode(self, file_flags: int, callback: Callable[[bytes, int], None],
                       data: bytes, offset: int) -> None:
                callback({}, offset)

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.exc_type, TypeError)
            self.assertIs(args.object, w)
            self.assertIn("bytes", str(args.exc_value), )
            self.assertIn("dict", str(args.exc_value), )

        w = EncodeCallbackTypeFailure()
        self.check_write(w, error_hook)
        self.assertExceptionLocation(w, "encode")

    def test_decode_callback_failure(self):
        class DecodeCallbackFailureNegativeLength(partial.UselessPartialIoWrapper):

            def decode(self, file_flags: int,
                       callback: Callable[[int, int], Union[bytes, bool]], length: int,
                       offset: int) -> Union[bytes, bool]:
                return callback(-1, offset)

        def error_hook(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.exc_type, ValueError)
            self.assertIs(args.object, w)
            self.assertIn("decode", str(args.exc_value), )
            self.assertIn("Negative", str(args.exc_value), )

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            error_hook(args)
            self.assertIn("length", str(args.exc_value), )

        w = DecodeCallbackFailureNegativeLength()
        self.check_connect(w, error_hook_)
        self.assertExceptionLocation(w, "decode")

        class DecodeCallbackFailureNegativeOffset(partial.UselessPartialIoWrapper):

            def decode(self, file_flags: int,
                       callback: Callable[[int, int], Union[bytes, bool]], length: int,
                       offset: int) -> Union[bytes, bool]:
                return callback(length, -1)

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            error_hook(args)
            self.assertIn("offset", str(args.exc_value), )

        w = DecodeCallbackFailureNegativeOffset()
        self.check_connect(w, error_hook_)
        self.assertExceptionLocation(w, "decode")

        class DecodeCallbackNoMemory(partial.UselessPartialIoWrapper):

            def decode(self, file_flags: int,
                       callback: Callable[[int, int], Union[bytes, bool]], length: int,
                       offset: int) -> Union[bytes, bool]:
                return callback(int(length * 1e90), offset)

        def error_hook_(args: UNRAISABLE_ARGS_TYPE):
            self.assertIs(args.exc_type, MemoryError)
            self.assertIs(args.object, w)

        w = DecodeCallbackNoMemory()
        self.check_connect(w, error_hook_)
        self.assertExceptionLocation(w, "decode")
