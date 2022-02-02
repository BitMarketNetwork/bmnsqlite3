import abc
import logging
import itertools
import os
import random
import secrets
import zlib
from base64 import urlsafe_b64decode as b64_out
from base64 import urlsafe_b64encode as b64_in
from typing import Any, Optional, Tuple, Union

from cryptography import fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from bmnsqlite3 import vfs
from tests import randbytes
from tests.wrappers import testcases

log = logging.getLogger(__name__)

AES_KEY_LENGTH = 32

SQLITE_OPEN_READONLY = 0x00000001
SQLITE_OPEN_READWRITE = 0x00000002
SQLITE_OPEN_CREATE = 0x00000004
SQLITE_OPEN_DELETEONCLOSE = 0x00000008
SQLITE_OPEN_EXCLUSIVE = 0x00000010
SQLITE_OPEN_AUTOPROXY = 0x00000020
SQLITE_OPEN_URI = 0x00000040
SQLITE_OPEN_MEMORY = 0x00000080
SQLITE_OPEN_MAIN_DB = 0x00000100
SQLITE_OPEN_TEMP_DB = 0x00000200
SQLITE_OPEN_TRANSIENT_DB = 0x00000400
SQLITE_OPEN_MAIN_JOURNAL = 0x00000800
SQLITE_OPEN_TEMP_JOURNAL = 0x00001000
SQLITE_OPEN_SUBJOURNAL = 0x00002000
SQLITE_OPEN_SUPER_JOURNAL = 0x00004000

SQLITE_ACCESS_EXISTS = 0
SQLITE_ACCESS_READWRITE = 1
SQLITE_ACCESS_READ = 2

backend = default_backend()


def trace_bytes(data: bytes) -> str:
    return f"{len(data)} data:{data[:5]}...{data[-5:]}"


class DecodeError(RuntimeError):

    def __init__(self, data: bytes, origin: Exception, **kwargs) -> None:
        super().__init__(f"{trace_bytes(data)}  // {origin} // {kwargs}")
        self.offset = kwargs.get("offset", None)
        self.length = len(data)
        self.data = data


class SectorSizeMixin:
    SECTOR_SIZE = 4096

    def sector_size(self, fh: Any) -> Optional[float]:
        return self.SECTOR_SIZE

    def device_characteristics(self, fh: Any) -> Optional[int]:
        return 0x00000020


class UselessMixin:
    """
    Does nothing with data
    """

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return data

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        return data


class EncodeMixin(abc.ABC):

    def _init_algo(self, key: Optional[bytes]) -> None:
        self._rnd_key = key is None

    @property
    def persistent(self) -> bool:
        return getattr(self, "_rnd_key", False)


class XorMixin(EncodeMixin):

    def __xor(self, data: bytes) -> bytes:
        return bytes(a ^ b for (a, b) in zip(data, self._gen_key(len(data))))

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return self.__xor(data)

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        """
        symmetric
        """
        return self.__xor(data)

    @staticmethod
    def _gen_key(size: int) -> bytes:
        # hardcoded seed
        random.seed(0x1000)
        return randbytes(size)


class Base64Mixin(EncodeMixin):

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return b64_in(data)

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        r = b64_out(data)
        if not r:
            raise DecodeError(data, Base64Mixin, **kwargs)
        return r


class ZipMixin(EncodeMixin):

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return b64_in(zlib.compress(data, 9))

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        try:
            return zlib.decompress(b64_out(data))
        except zlib.error as ze:
            raise DecodeError(data, ze, **kwargs) from ze


class MixBytesMixin:
    """
    data mixed with random data and reversed
    i.e. [1,2,3,4] => [<rnd>,4 ^ <rnd>,<rnd>,3 ^ <rnd>,<rnd>,2 ^ <rnd>,<rnd>,1 ^ <rnd>]
    where <rnd> is next random byte (not the same of course)
    """

    def mix(self, data: bytes, **kwargs) -> bytes:
        return bytes(itertools.chain.from_iterable(zip(data, randbytes(len(data)))))[::-1]

    def demix(self, data: bytes, **kwargs) -> bytes:
        return data[::-2]


class AesCfbMixin(EncodeMixin):
    """
    AES CFB ( no padding)

    less secure - no HMAC and timestamp
    """

    def _init_algo(self, key: Optional[bytes]) -> None:
        super()._init_algo(key)
        self.__algo = algorithms.AES(key or os.urandom(AES_KEY_LENGTH))

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        iv = secrets.token_bytes(self.__algo.block_size // 8)
        cipher = Cipher(self.__algo, modes.CFB(iv), backend=backend)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return b64_in(iv + ciphertext)

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        iv_ciphertext = b64_out(data)
        size = self.__algo.block_size // 8
        iv, encrypted = iv_ciphertext[:size], iv_ciphertext[size:]
        cipher = Cipher(self.__algo, modes.CFB(iv), backend=backend)
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted) + decryptor.finalize()


class AesEcbMixin(EncodeMixin):
    """
    AES ECB

    not secure for real time routines!!!!
    """

    def _init_algo(self, key: Optional[bytes]) -> None:
        super()._init_algo(key)
        self.__algo = algorithms.AES(key or os.urandom(AES_KEY_LENGTH))

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        cipher = Cipher(self.__algo, modes.ECB(), backend=backend)
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(cipher.algorithm.block_size).padder()
        padded = padder.update(data) + padder.finalize()
        return b64_in(encryptor.update(padded) + encryptor.finalize())

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        cipher = Cipher(self.__algo, modes.ECB(), backend=backend)
        decryptor = cipher.decryptor()
        unpadder = padding.PKCS7(cipher.algorithm.block_size).unpadder()
        padded = decryptor.update(b64_out(data)) + decryptor.finalize()
        return unpadder.update(padded) + unpadder.finalize()


class FernetMixin(EncodeMixin):
    """
    Fernet uses AES CBC + HMAC https://github.com/fernet/spec/blob/master/Spec.md

    The must secured and recommended way to encrypt data (though asymmetric encryption could be more safe)
    """

    def _init_algo(self, key: Optional[bytes]) -> None:
        super()._init_algo(key)
        self.__f = fernet.Fernet(key or fernet.Fernet.generate_key())

    def encrypt(self, data: bytes, **kwargs) -> bytes:
        return self.__f.encrypt(data)

    def decrypt(self, data: bytes, **kwargs) -> bytes:
        try:
            return self.__f.decrypt(data)
        except fernet.InvalidToken as it:
            raise DecodeError(data, it) from it


class IOpenMixin(abc.ABC):

    def open(self, path: str, flags: int) -> Union[Any, Tuple[Any, int]]:
        mode = None
        if flags & SQLITE_OPEN_READONLY:
            mode = "rb"
        if flags & SQLITE_OPEN_READWRITE:
            mode = "rb+"
        if flags & SQLITE_OPEN_EXCLUSIVE:
            assert flags & SQLITE_OPEN_CREATE
            os.remove(path)
        elif flags & SQLITE_OPEN_CREATE:
            if not os.path.exists(path):
                mode = "wb+"
        assert mode
        # TODO: check and cover all WRONG access types
        # 'cause this method might be working, but not straight errors will be later
        try:
            return open(path, mode)
        except OSError as oe:
            log.error("Open error:%s path: %s flags:%s mode:%s",
                      oe, path, flags, mode)
            raise

class IDeleteMixin(abc.ABC):
    

    def delete(self, path: str, sync_dir: bool) -> None:
        os.remove(path=path)
        

class FillGapMixin(abc.ABC):
    """
    Actually you don't need this mixin for the most cases

    But without it you can meet some hard to debug errors if you call VACUUM command.
    So you have two choises:
     - deny VACUUM via file_control method
     - use gap detection features ( see  'FillGapWithZerosMixin')
    """

    @abc.abstractclassmethod
    def generate_gap(self, length: int, **kwargs) -> bytes:
        """
        generates data to fill space in DB
        """

    @abc.abstractclassmethod
    def detect_gap(self, data: bytes, **kwargs) -> bool:
        """
        detects gap
        returns True if data recognized as gap and shouldn't be decoded
        """


class FillGapRandomMixin(FillGapMixin):
    """
    We fill gap with random data and deny VACUUM

    There is one advatage at least to use this mixin - more secure data, 'cause isn't easy to distinguish gap (random) data from real data
    """

    def generate_gap(self, length: int, **kwargs) -> bytes:
        return randbytes(length)

    def detect_gap(self, data: bytes, **kwargs) -> bool:
        return False

    def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
        return 11 == operation


class FillGapWithZerosMixin(FillGapMixin):
    """
    We fill gap with zeros and then detect it

    """

    def generate_gap(self, length: int, **kwargs) -> bytes:
        return bytes(length)

    def detect_gap(self, data: bytes, **kwargs) -> bool:
        """
        detect zeros
        """
        return not any(b for b in data)


class FillGapWithZerosFastMixin(FillGapWithZerosMixin):
    """
    It possible to work it faster specifing HEAD_LENGTH 
    
    """
    HEAD_LENGTH = 4

    def detect_gap(self, data: bytes, **kwargs) -> bool:
        """
        detect zeros
        """
        return not any(b for b in data[:self.HEAD_LENGTH])


class IFullTestWrapper(vfs.IFullVfsWrapper, testcases.ITestMixin, abc.ABC):
    pass


class IPartialTestWrapper(vfs.IPartialVfsWrapper, testcases.ITestMixin, abc.ABC):
    pass
