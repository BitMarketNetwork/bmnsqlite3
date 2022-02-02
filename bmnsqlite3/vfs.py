import abc
from typing import Any, Optional, Callable, Union, Tuple

"""
API description:

Module has two methods:

- **vfs_register**(wrapper: object, make_default : Bool = True) - register class instance as a wrapper
    for some sqlite operations.
    Description of the wrapper class is down below.
    There are two approaches to implement it.
    Use None as argument to remove (unregister) wrapper.
    
    Args:
        wrapper (object): Class instance used as a wrapper for FVS operations. Can be inherited from IVfsWrapper for 
        facilitation (look down below). 
        Use None to unregister current wrapper. make_default means nothing in that case.
        make_default (bool):  Use wrapper as a default. Setting this to False in current implementation has no sense.

    Returns:
        None

- **vfs_find**(vfs_name : Optional[str] = None) - retrieve currently used wrapper or
    None if no wrapper is registered.

    Args:
        vfs_name (Optional[str]): Reserved for future use.

    Returns:
        Find currently registered wrapper instance or None 
"""

"""
Errors handling

To catch errors from wrapper use this code
```
        def error_hook(args):
            print(args.exc_value)
            print(args.object)
            print(args.exc_traceback) # or something...

        sys.unraisablehook = error_hook
```
Avoid making mistakes in this hook, cause' it'll be ignored
See:
https://vstinner.github.io/sys-unraisablehook-python38.html
Also pay attention that behavior of sys.unraisablehook in python3.7.x differs: just printing to stderr used.
"""

"""
Debugging API

When module compiled with REGISTER_DEBUG_ITEMS==1 compile flag some extra API become avialable.
This flag turned off when NDEBUG defined.
ANy of these items can be removed in future

- **connections_count**() - returns opened connection count of currently used VFS. Only BMN VFS supported

- When exception raised in wrapper's method wrapper attribute by name **exception_location** contains 
    method name where exception raised. This information is neccesary for unit testing.


- 

"""


class IVfsWrapper(abc.ABC):

    def full_pathname(self, name: str, out: int) -> Optional[str]:
        """
        Method should return full pathname to file 'name'.
        Result string size must be less or equal 'out'
        Returning None gives no errors.

        Args:
            name (str): Name of the file
            out (int):  Maximum result length

        Returns:
            Optional[str]: Full path name or None to choose default behaviour
        """

    def random(self, size: int) -> Optional[bytes]: 
        """
        Method should return 'size' bytes of good-quality randomness 

        Args:
            size (int): Count of bytes to return

        Returns:
            Optional[int]: 'size' bytes of good-quality randomness or None to choose default behaviour
        """

    def current_time(self) -> Optional[float]: 
        """
        Method  returns a current time

        Returns:
            Optional[float]: Julian Day Number for the current date and time as a floating point value or None to choose default behaviour
        """

    def current_time_int64(self) -> Optional[int]: 
        """
        Method  returns a current time

        Returns:
            Optional[int]: returns, as an integer, the Julian Day Number multiplied by 86400000 (the number of milliseconds in a 24-hour day) or None to choose default behaviour
        """

    def delete(self, path: str, sync_dir: bool) -> None:
        """
        It is optional method, but it is crusial for right functioning.
        For this purpose this absract method raises exception.

        Args:
            path (str): file path to delete
            sync_dir (bool): 
        """
        raise NotImplementedError

class IFullVfsWrapper(IVfsWrapper):

    @abc.abstractmethod
    def open(self, path: str, flags: int) -> Union[Any, Tuple[Any, int]]:
        """ The key method in wrapper. The file can be not only DB file.
         There are many file types: main database,
         temporary database, journal and wall files.

        Important remark: if this method not implemented in wrapper,
            then bmnsqlite3 treats this wrapper as partial so it must implement
            another (Partial) interface.
            See IPartialVfsWrapper class down below.

        Args:
            path (str): File path
            flags (int): File flags. See:
                https://www.sqlite.org/c3ref/c_open_autoproxy.html

        Returns:
            Union[Any, Tuple[Any, int]]: Feel free to return any (non scalar)
                value or object which will be used later
                to access the storage in other methods. It may be file
                handler or any another object.
                It is possible also to return opening
                flags for file in second item in tuple
        """

    def access(self, path: str, flags: int) -> Optional[bool]:
        """ Test file access (see flags)
        Method is optional

        Args:
            path (str): File path, can be a directory
            flags (int):
                SQLITE_ACCESS_EXISTS to test for the existence of a file
                SQLITE_ACCESS_READWRITE to test whether a file
                is readable and writable
                SQLITE_ACCESS_READ to test whether a file is at least readable.
                    The SQLITE_ACCESS_READ flag is never actually used and
                    is not implemented
                    in the built-in VFSes of SQLite.

        Returns:
            bool: return True to indicate whether or not the file is accessible.
        """

    @abc.abstractmethod
    def close(self, fh: Any) -> None:
        """
        Mandatory method in case 'open' method is implemented

        Args:
            fh (Any): Value returned from 'open' method to release. For example file handler to close.
        """

    @abc.abstractmethod
    def write(self, fh: Any, data: bytearray, offset: int) -> None: 
        """
        This method must be implemented if 'open' method also implemented.
        It used to write data to file system or any another storage


        Args:
            fh (Any): Value returned from 'open' method
            data (bytearray): Data which this method should write
            offset (int): Offset to place data
        """

    @abc.abstractmethod
    def read(self, fh: Any, length: int, offset: int) -> Union[bytearray, bool]:
        """
        This method must be implemented if 'open' method also implemented.
        It used to read data from file system or any another storage

        Args:
            fh (Any): Value returned from 'open' method
            length (int): Bytes to return
            offset (int): Offset to read from

        Returns:
            Optional[bytearray]: it must be either
                bytearray with 'length' size or False
                in case there are no enough bytes to read this size.
                Any another results are treated as errors
        """

    @abc.abstractmethod
    def truncate(self, fh: Any, size: int) -> None: 
        """
        Method truncates file to 'size'

        Args:
            fh (Any): File handler
            size (int): Size to truncate to
        """

    @abc.abstractmethod
    def file_size(self, fh: Any) -> int: 
        """
        Returns file size

        Args:
            fh (Any): File handle

        Returns:
            int: File size in bytes
        """

    def device_characteristics(self, fh: Any) -> Optional[int]:
        """
        It is possible not to implement this method,
        then default value (SQLITE_IOCAP_UNDELETABLE_WHEN_OPEN) will be used.
        Even if you make a mistake here.
        Returning None gives no errors.

        Args:
            fh (Any): Value returned from 'open' method

        Returns:
            int: Sum of flags.
                See: https://www.sqlite.org/c3ref/c_iocap_atomic.html
        """

    def sector_size(self, fh: Any) -> Optional[float]:
        """It is possible not to implement this method, then default
        value (4096) will be used.
        Even if you make a mistake here.
        Returning None gives no errors.

        This method is important for customizing read/write operations

        Args:
            fh (Any): Value returned from 'open' method

        Returns:
            int:  The sector size of the device that underlies the file.
            The sector size is the minimum write that can be performed
            without disturbing other bytes in the file
        """

    def sync(self, fh: Any, flags: int) -> None:
        """

        Args:
            fh (Any): 
            flags (int): 

        Returns:
            [type]: 
        """

    def file_control(self, fh: Any, operation: int, argument: Any) -> bool:
        """
        Optional method to handle some sqlite operations

        Args:
            fh (Any): Value returned from 'open' method]
            operation (int): Operation number
            argument (Any): Variant argument depening on operation

        Returns:
            bool: Return True to change default beahavior depending on operation. 
                False is default
        """

class IPartialVfsWrapper(IVfsWrapper):
    """ There are two approaches to implement wrapper: full and partial.
    If 'open' method is implemented then this wrapper is treated
    as full one, either it will be treated as partial one.
    The main difference: in full wrapper
    python code controls all file operations.
    However in partial implementation bmnsqlite3 owns file handle and
    allows python code to customize only IO operations.
    Both implementations have advantages and disadvantages.
    """

    @abc.abstractmethod
    def encode(self, file_flags: int, callback: Callable[[bytes, int], int],
               data: bytes, offset: int) -> None:
        """ Encode bytes given in argument 'data' with 'offset' and fee it to
            function 'callback'

        Args:
            file_flags (int): Flags of file used here
            callback (Callable[[ bytes, int], int]): Target function
            data (bytes): Source data
            offset (int): Offset in data
        """

    @abc.abstractmethod
    def decode(self, file_flags: int,
               callback: Callable[[int, int], Union[bytes, bool]], length: int,
               offset: int) -> \
            Union[bytes, bool]:
        """ Decode bytes returned by calling function 'callback'. Callback can
        return bool (False) if is impossible to read this piece of data.
        This method also should return bool(False) if is impossible
        to read, but it doesn't mean that second cases comes from the first one!
        Callback arguments are length and offset.

        Args:
            file_flags (int): Flags of file used here
            callback (Callable[[int, int], Union[bytes, bool]]): Source function
            length (int): Length of data to read
            offset (int): Offset in data

        Returns:
            Union[bytes, bool]: Result bytes or False if reading isn't available
        """
