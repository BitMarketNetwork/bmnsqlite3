import abc
import logging
import struct
from typing import Callable, Union

from tests import randbytes
from tests.wrappers import abstract, minimal

log = logging.getLogger(__name__)

ENCODE_CALLBACK_SIGNATURE = Callable[[bytes, int], None]
# depends on BMN_MARK_SHORT_READ_WITH_BOOL
# DECODE_CALLBACK_SIGNATURE = Callable[[int, int], Optional[bytes]]
DECODE_CALLBACK_SIGNATURE = Callable[[int, int], Union[bytes, bool]]
"""
We can't set sector size to sqlite3, because we don't own the DB file
So use default sector size
"""
DEFAULT_SECTOR_SIZE = 4096


class UselessPartialIoWrapper(minimal.MinimalPartialWrapper):
    """
    Partial implementation doesn't override wrapper's 'open' method, so all sqlite files are handled by sqlite3
    So we have no responsibility for overriding a lot of sqlite3 methods, but we have to override both of IO operations

    This wrapper does nothing but overrides IO stuff
    """


class XorPartialIoWrapper(abstract.IPartialTestWrapper, abstract.XorMixin):
    """
    This version does primitive IO encoding via XOR operation with random bytes
    """

    def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> None:
        callback(self.encrypt(data), offset)

    def decode(self, file_flags: int, callback: Callable[[int, int], Union[bytes, bool]], length: int, offset: int) -> \
            Union[bytes, bool]:
        data = callback(length, offset)
        # it's important to handle case When callback returns Bool(False). It's normal behavior
        if data:
            return self.decrypt(data)
        return data


class ISectorSizePartialWrapper(abstract.IPartialTestWrapper, abstract.EncodeMixin, abc.ABC):
    """Align written data by sectors and alloc more space as we can change written data length"""
    RATIO = 2

    def __init__(self) -> None:
        super().__init__()
        self._init_algo(None)

    def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> None:
        if file_flags & abstract.SQLITE_OPEN_MAIN_DB == 0:
            return callback(data, offset)
        offset *= self.RATIO
        enc = self.encrypt(data)
        add_len = len(data) * self.RATIO - len(enc)
        assert add_len >= 0, "Too small ratio %d < %f. %s // %s" % (
            self.RATIO, len(enc) / len(data), file_flags, len(data))
        return  callback(enc + add_len * b'0', offset)

    def decode(self, file_flags: int, callback: DECODE_CALLBACK_SIGNATURE, length: int, offset: int) -> Union[
        bytes, bool]:
        if file_flags & abstract.SQLITE_OPEN_MAIN_DB == 0:
            return callback(length, offset)
        offset *= self.RATIO
        tail = offset % DEFAULT_SECTOR_SIZE
        offset -= tail
        read_length = 0
        while read_length < length:
            read_length += DEFAULT_SECTOR_SIZE
        read_length *= self.RATIO
        data = callback(read_length, offset)
        # it's dangerous to check that .. what about empty array?
        # if data:
        if not isinstance(data, bool):
            return self.decrypt(data)[tail:length + tail]
        return data


class IFixedLengthWrapper(abstract.IPartialTestWrapper, abstract.EncodeMixin, abc.ABC):
    """Prepend encrypted data with its length and don't forget about sectors"""

    """
    must cover AES overhead
    it can be smaller but adopt code to float values
    """
    RATIO = 2

    def __init__(self) -> None:
        super().__init__()
        self._init_algo(None)

    def encode(self, file_flags: int, callback: ENCODE_CALLBACK_SIGNATURE, data: bytes, offset: int) -> None:
        if file_flags & abstract.SQLITE_OPEN_MAIN_DB == 0:
            callback(data, offset)
        else:
            offset *= self.RATIO
            enc = self.encrypt(data)
            add_len = len(data) * self.RATIO - len(enc) - 4
            assert add_len >= 0, "Too small ratio %d < %f" % (
                self.RATIO, len(enc) / len(data))
            enc_length = struct.pack(">I", len(enc))
            callback(enc_length + enc + randbytes(add_len), offset)

    def decode(self, file_flags: int, callback: Callable[[int, int], Union[bytes, bool]], length: int, offset: int) -> \
            Union[bytes, bool]:
        if file_flags & abstract.SQLITE_OPEN_MAIN_DB == 0:
            return callback(length, offset)
        offset *= self.RATIO
        tail = offset % DEFAULT_SECTOR_SIZE
        offset -= tail
        read_length_bytes = callback(4, offset)
        if read_length_bytes:
            read_length = struct.unpack(">I", read_length_bytes)[0]
            data = callback(read_length, offset + 4)
            if data:
                return self.decrypt(data)[tail:length + tail]
        return False


class ZipPartialWrapper(ISectorSizePartialWrapper, abstract.ZipMixin):
    pass


class AesCfbPartialWrapper(ISectorSizePartialWrapper, abstract.AesCfbMixin):
    pass


class AesEcbPartialWrapper(IFixedLengthWrapper, abstract.AesEcbMixin):
    pass


class FernetPartialWrapper(IFixedLengthWrapper, abstract.FernetMixin):
    pass
