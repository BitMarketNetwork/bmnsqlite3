import os
from typing import Any, Optional, Union, Callable

from tests.wrappers import abstract


class MinimalFullWrapper(abstract.IOpenMixin, abstract.IFullTestWrapper):
    """
    this wrapper does nothing
    the main purpose - to be valid with minimum implemented methods
    """

    def close(self, fh: Any) -> None:
        fh.close()

    def truncate(self, fh: Any, size: int) -> None:
        # take care! python truncate implementation is treaky!
        fh.truncate(size)

    def write(self, fh: Any, data: bytes, offset: int) -> None:
        fh.seek(offset, os.SEEK_SET)
        fh.write(data)

    def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
        fh.seek(0, os.SEEK_END)
        if fh.tell() >= length + offset:
            fh.seek(offset, os.SEEK_SET)
            return fh.read()[:length]
        return False

    def file_size(self, fh: Any) -> int:
        # there are many ways to solve it and this is paranoid one
        old_file_position = fh.tell()
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(old_file_position, os.SEEK_SET)
        return size


class MinimalPartialWrapper(abstract.IPartialTestWrapper):
    """
    this wrapper does nothing
    the main his purpose - to be valid with minimum implemented methods
    """

    def encode(self, file_flags: int, callback: Callable[[bytes, int], None],
               data: bytes, offset: int) -> None:
        return callback(data, offset)

    def decode(self, file_flags: int,
               callback: Callable[[int, int], Union[bytes, bool]], length: int,
               offset: int) -> Union[bytes, bool]:
        return callback(length, offset)
