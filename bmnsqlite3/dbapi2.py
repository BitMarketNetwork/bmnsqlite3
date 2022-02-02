# https://www.python.org/dev/peps/pep-0249/
import datetime
import time
import collections.abc

from _bmnsqlite3 import *

# String constant stating the supported DB API level.
apilevel = "2.0"

# Integer constant stating the level of thread safety the interface supports.
threadsafety = 1

# String constant stating the type of parameter marker formatting expected by
# the interface.
paramstyle = "qmark"

# This function constructs an object holding a date value.
# Date(year, month, day)
Date = datetime.date

# This function constructs an object holding a time value.
# Time(hour, minute, second)
Time = datetime.time

# This function constructs an object holding a time stamp value
# Timestamp(year, month, day, hour, minute, second)
Timestamp = datetime.datetime


# This function constructs an object holding a date value from the given ticks
# value.
def DateFromTicks(ticks: int) -> Date:
    return Date(*time.localtime(ticks)[:3])


# This function constructs an object holding a time stamp value from the given
# ticks value
def TimeFromTicks(ticks: int) -> Time:
    return Time(*time.localtime(ticks)[3:6])


# This function constructs an object holding a time stamp value from the given
# ticks value.
def TimestampFromTicks(ticks: int) -> Timestamp:
    return Timestamp(*time.localtime(ticks)[:6])


# This function constructs an object capable of holding a binary (long) string
# value.
# Binary(string)
Binary = memoryview

# This type object is used to describe columns in a database that are
# string-based (e.g. CHAR).
STRING = str

# This type object is used to describe (long) binary columns in a database
# (e.g. LONG, RAW, BLOBs).
BINARY = bytes

# This type object is used to describe numeric columns in a database.
NUMBER = int

# This type object is used to describe date/time columns in a database.
DATETIME = Timestamp

# This type object is used to describe the "Row ID" column in a database.
ROWID = int


# from original sqlite3 package
version_info = tuple(int(x) for x in version.split("."))
sqlite_version_info = tuple(int(x) for x in sqlite_version.split("."))
collections.abc.Sequence.register(Row)  # noqa


def _register_adapters_and_converters() -> None:
    def adapt_date(value: Date) -> str:
        return value.isoformat()

    def adapt_timestamp(value: Timestamp) -> str:
        return value.isoformat(" ")

    def convert_date(value: bytes) -> Date:
        return Date(*map(int, value.split(b"-")))

    def convert_timestamp(value: bytes) -> Timestamp:
        date_, time_ = value.split(b" ")
        year, month, day = map(int, date_.split(b"-"))
        time_ = time_.split(b".")

        hours, minutes, seconds = map(int, time_[0].split(b":"))
        if len(time_) == 2:
            microseconds = int('{:0<6.6}'.format(time_[1].decode()))
        else:
            microseconds = 0

        return Timestamp(
            year,
            month,
            day,
            hours,
            minutes,
            seconds,
            microseconds)

    register_adapter(Date, adapt_date)
    register_adapter(Timestamp, adapt_timestamp)
    register_converter("date", convert_date)
    register_converter("timestamp", convert_timestamp)


_register_adapters_and_converters()
del _register_adapters_and_converters
