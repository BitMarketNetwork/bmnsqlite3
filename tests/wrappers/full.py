import abc
import logging
import os
import time
import math
from datetime import datetime
from typing import Any, Optional, Union

from tests import randbytes
from tests.wrappers import abstract, minimal

log = logging.getLogger(__name__)


def julian_day(date: datetime) -> int:
    julian_datetime = 367 * date.year - int((7 * (date.year + int((date.month + 9) / 12.0))) / 4.0) + int(
        (275 * date.month) / 9.0) + date.day + 1721013.5 + (
        date.hour + date.minute / 60.0 + date.second / math.pow(60,
                                                                2)) / 24.0 - 0.5 * math.copysign(
        1, 100 * date.year + date.month - 190002.5) + 0.5

    return julian_datetime

# attention! strict inheritance order! tough to debug ..


class ISimpleWrapper(minimal.MinimalFullWrapper):
    """
    Simple wrapper implementation.
    This wrapper has not correct read/write method bindings...
    It ought to be fixed in children classes
    """

    @abc.abstractmethod
    def encrypt(self, data: bytes, **kwargs) -> bytes:
        """
        kwargs used for debugging purposes
        raise exception to avoid unexpected behavior in inheritance chains
        """
        raise NotImplementedError

    @abc.abstractmethod
    def decrypt(self, data: bytes, **kwargs) -> bytes:
        """
        kwargs used for debugging purposes
        raise exception to avoid unexpected behavior in inheritance chains
        """
        raise NotImplementedError

    def open(self, path: str, flags: int) -> Any:
        fh = super().open(path, flags)
        # encrypt only DB file, but not journals or wal-s ...
        # but this actually doesn't affect anything for a while .. just testing this feature
        fh.encode = (flags & abstract.SQLITE_OPEN_MAIN_DB) != 0
        # to debug
        fh.filename = path
        return fh

    def access(self, path: str, flags: int) -> Optional[bool]:
        mode = os.F_OK
        if flags == abstract.SQLITE_ACCESS_READWRITE:
            mode = os.R_OK | os.W_OK
        if flags == abstract.SQLITE_ACCESS_READ:
            mode = os.R_OK
        return os.access(path, mode)

    def full_pathname(self, name: str, out: int) -> Optional[str]:
        if name.startswith("/"):
            return name[1:]
        return name

    def delete(self, path: str, sync_dir: bool) -> None:
        os.remove(path)

    def write(self, fh: Any, data: bytes, offset: int) -> None:
        fh.seek(offset, os.SEEK_SET)
        if fh.encode:
            fh.write(self.encrypt(data, offset=offset))
        else:
            fh.write(data)

    def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
        fh.seek(0, os.SEEK_END)
        if fh.tell() >= length + offset:
            fh.seek(offset, os.SEEK_SET)
            if fh.encode:
                res = self.decrypt(fh.read())
            else:
                res = fh.read()
            return res[:length]
        return False

    def random(self, size: int) -> bytes:
        return os.urandom(size)

    def current_time(self) -> float:
        return datetime.now().timestamp()

    def current_time_int64(self) -> int:
        return (julian_day(datetime.now())) * 86400000

    def device_characteristics(self, fh: Any) -> Optional[int]:
        # remember sector size issue!!
        return 0x800 + 0x1000

    def validate(self) -> bool:
        data = randbytes(0x1000)
        enc = self.encrypt(data, offset=0)
        # test for None because not easy to catch abstract call
        return enc is not None and data != enc and data == self.decrypt(enc, offset=0)


class IFixedRatioWrapper(ISimpleWrapper, abstract.FillGapMixin, abc.ABC):
    """
    In this implementation we assume that our encoded binary takes place not more than FACTOR times of source length
    """
    RATIO = 2

    def write(self, fh: Any, data: bytes, offset: int) -> None:
        if not fh.encode:
            return super().write(fh, data, offset)
        offset *= self.RATIO
        fh.seek(offset, os.SEEK_SET)
        enc = self.encrypt(data, offset=offset)
        add_len = len(data) * self.RATIO - len(enc)
        assert add_len >= 0, "Too small ratio %d < %f" % (
            self.RATIO, len(enc) / len(data))
        fh.write(enc + self.generate_gap(add_len, offset=offset))

    def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
        if not fh.encode:
            return super().read(fh, length, offset)
        fh.seek(0, os.SEEK_END)
        offset *= self.RATIO
        if fh.tell() >= length * self.RATIO + offset:
            fh.seek(offset, os.SEEK_SET)
            try:
                res = self.safe_decrypt(
                    fh.read(length * self.RATIO), offset=offset)
            except abstract.DecodeError as de:
                log.error("Decode failure at: %s", fh.filename)
                raise
            return res[:length]
        return False

    def truncate(self, fh: Any, size: int) -> None:
        """
        important to adjust this call to make sure that such sqlite commands like VACUUM and other work correctly
        """
        if self.file_size(fh) > size * self.RATIO:
            super().truncate(fh, size * self.RATIO)

    def safe_decrypt(self, data: bytes, **kwargs) -> bytes:
        if self.detect_gap(data, **kwargs):
            return data
        return self.decrypt(data, **kwargs)


class UselessWrapper(abstract.UselessMixin, ISimpleWrapper, ):
    def validate(self) -> bool:
        # we should skip validation, cause validation process tests
        # that encoded data differ from source data
        # but this wrapper doesn't do anything at all with source
        return True


class XorWrapper(abstract.XorMixin, ISimpleWrapper, ):
    pass


class Base64Wrapper(abstract.Base64Mixin, abstract.FillGapWithZerosMixin, IFixedRatioWrapper, ):
    pass


class XorMixWrapper(abstract.XorMixin, abstract.MixBytesMixin, abstract.FillGapWithZerosMixin, IFixedRatioWrapper,):
    """
    XOR mixed with random data and reversed
    i.e. [1,2,3,4] => [<rnd>,4 ^ <rnd>,<rnd>,3 ^ <rnd>,<rnd>,2 ^ <rnd>,<rnd>,1 ^ <rnd>]
    where <rnd> is next random byte (not the same of course)
    """
    RATIO = 2

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return self.mix(super().encrypt(data))

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        return super().decrypt(self.demix(data), **kwargs)


class SleepWrapper(XorWrapper):
    """
    delay simulation
    It's made to check some debug cases
    """

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        time.sleep(0.01)
        return super().encrypt(data, **kwargs)
