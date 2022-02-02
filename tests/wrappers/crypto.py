import abc
from bmnsqlite3.dbapi2 import Date
import logging
import os
import struct
from typing import Any, Optional, Union

from tests import randbytes
from tests.wrappers import abstract
from tests.wrappers import full

log = logging.getLogger(__name__)


class ISectorWrapper(full.IFixedRatioWrapper, abstract.SectorSizeMixin, abc.ABC):
    """
    abstract wrapper that stick to sector size
    for example XOR or BASE64 doesn't need to follow sectors ( because no format headers and so on)
    """
    RATIO = 2

    def write(self, fh: Any, data: bytes, offset: int) -> None:
        return super().write(fh, data, offset)

    def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
        if not fh.encode:
            return super().read(fh, length, offset)
        fh.seek(0, os.SEEK_END)
        offset *= self.RATIO
        # whether file is large enugh
        if fh.tell() >= length * self.RATIO + offset:
            tail = offset % self.SECTOR_SIZE
            offset -= tail
            fh.seek(offset, os.SEEK_SET)
            read_length = 0
            while read_length < length:
                read_length += self.SECTOR_SIZE
            read_length *= self.RATIO
            res = self.safe_decrypt(fh.read(read_length), offset=offset)
            return res[tail:length + tail]
        return False

    def device_characteristics(self, fh: Any) -> Optional[int]:
        return 0x00000010 + 0x00000400


class ICryptoMixin(abstract.EncodeMixin, abc.ABC):
    persistent = False

    def __init__(self, key: Optional[bytes] = None) -> None:
        super().__init__()
        self._init_algo(key)


class ZipWrapper(ICryptoMixin, abstract.ZipMixin, abstract.FillGapWithZerosMixin, ISectorWrapper, ):
    pass

class ZipFastWrapper(ICryptoMixin, abstract.ZipMixin, abstract.FillGapWithZerosFastMixin, ISectorWrapper, ):
    pass

class ZipMessyWrapper(ICryptoMixin, abstract.ZipMixin, abstract.FillGapRandomMixin, ISectorWrapper, ):
    pass

class AesCfbWrapper(ICryptoMixin, abstract.AesCfbMixin, abstract.FillGapWithZerosMixin, ISectorWrapper):
    pass

class IFixedLengthWrapper(ISectorWrapper, abstract.FillGapWithZerosMixin, abc.ABC):
    """
    The must severe version where we must save length of the encrypted data  in the prefix
    We also use ratio to alloc more space to avoid rewrite previous sector

    Fill gap with zeros here (see FillGapWithZerosMixin in MRO), but any other approach can be applied 
    
    Also pay attention this 'read' version works much faster because we avoid calling ptoentially much slower 'safe_decrypt'
    """
    RATIO = 2

    def write(self, fh: Any, data: bytes, offset: int) -> None:
        if not fh.encode:
            return super().write(fh, data, offset)

        enc = self.encrypt(data, offset=offset)
        offset *= self.RATIO
        fh.seek(offset, os.SEEK_SET)
        length = struct.pack(">I", len(enc))
        add_len = len(data) * self.RATIO - 4 - len(enc)
        assert add_len >= 0, "Too small ratio %d < %f" % (
            self.RATIO, len(enc) / len(data))
        fh.write(length + enc + self.generate_gap(add_len))

    def read(self, fh: Any, length: int, offset: int) -> Union[bytes, bool]:
        if not fh.encode:
            return super().read(fh, length, offset)

        fh.seek(0, os.SEEK_END)
        offset *= self.RATIO
        if fh.tell() >= length * self.RATIO + offset:
            tail = offset % self.SECTOR_SIZE
            offset -= tail
            fh.seek(offset, os.SEEK_SET)
            read_length = struct.unpack(">I", fh.read(4))[0]
            # gap gives zero length anyway in this case
            if read_length:
                # we don't need to be safe
                # res = self.safe_decrypt(fh.read(read_length), offset=offset)
                res = self.decrypt(fh.read(read_length), offset=offset)
            else:
                res = fh.read(length)
            return res[tail:length + tail]
        return False



class AesEcbWrapper(ICryptoMixin, abstract.AesEcbMixin,  IFixedLengthWrapper):
    pass


class FernetWrapper(ICryptoMixin, abstract.FernetMixin,  IFixedLengthWrapper):
    pass


class PersistentFernetIoWrapper(FernetWrapper):
    pass

    def __init__(self) -> None:
        super().__init__(b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=')
