from __future__ import annotations
import abc
import logging
import random
import sqlite3
import string
import time
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, date
from typing import Optional, Tuple

import bmnsqlite3
from tests import randbytes, str_generator

log = logging.getLogger(__name__)

SHOW_QUERIES = True


def execute(cursor: sqlite3.Cursor, query: str, data: tuple = ()) -> sqlite3.Cursor:
    """
     wrap to debug
    """
    assert isinstance(cursor, (bmnsqlite3.Cursor, sqlite3.Cursor)
                      ), "bad cursor type: %s" % type(cursor)
    if not isinstance(data, (tuple, list)):
        data = (data,)
    query_string = "'%s' with '%s'" % (
        query[:256], [str(d)[:100] for d in data]) if data else query
    (log.info if SHOW_QUERIES else log.debug)(query_string)
    try:
        return cursor.execute(query, data)
    except bmnsqlite3.IntegrityError:
        log.debug(f"Bad {query_string}")
        raise


class DbMixin(metaclass=abc.ABCMeta):
    table_name: str = None

    def __init__(self, *_, **__):
        self.id = None

    # for hinting
    def __len__(self) -> int: ...

    # for hinting
    def __iter__(self) -> iter: ...

    @property
    def question_marks(self, count: Optional[int] = None) -> str:
        return ','.join('?' * (count or len(self)))

    def write(self, cursor: sqlite3.Cursor) -> DbMixin:
        assert self.table_name
        execute(
            cursor, f"INSERT INTO {self.table_name} VALUES ({self.question_marks})", tuple(self))
        self.id = cursor.lastrowid
        return self

    def delete(self, cursor: sqlite3.Cursor, attr: str) -> None:
        assert self.table_name
        execute(
            cursor, f"DELETE FROM {self.table_name} WHERE {attr} = ?;", (getattr(self, attr),))

    def update(self, cursor: sqlite3.Cursor, attr: str, **kwargs) -> DbMixin:
        assert self.table_name
        assert kwargs
        set_ = ",".join((f"{key} = ?" for key in kwargs.keys()))
        execute(
            cursor, f"UPDATE {self.table_name} SET {set_} WHERE {attr} = ?;",
            tuple(list(kwargs.values()) + [getattr(self, attr)])
        )
        return self

    def get(self, cursor: sqlite3.Cursor, attr: str, *get_attrs) -> Tuple[str]:
        assert isinstance(cursor, (bmnsqlite3.Cursor,
                          sqlite3.Cursor)), f"bad {type(cursor)}"
        assert self.table_name
        to_get = ','.join(get_attrs)
        execute(
            cursor, f"SELECT {to_get} FROM {self.table_name} WHERE {attr} = ?;", (getattr(self, attr),))
        return cursor.fetchall()[0]

    def get_me(self, cursor: sqlite3.Cursor, attr: str) -> DbMixin:
        assert isinstance(cursor, (bmnsqlite3.Cursor, sqlite3.Cursor)
                          ), "bad cursor type: %s" % type(cursor)
        assert self.table_name
        data = execute(
            cursor, f"SELECT * FROM {self.table_name} WHERE {attr} = ?;", (getattr(self, attr),)).fetchone()
        return self.__class__(*data)

    @ classmethod
    @ abc.abstractmethod
    def create(cls, cursor: sqlite3.Cursor, table: str, exec_: bool = False) -> str:
        cls.table_name = table
        return ""


# the fields order is messy intentionally
AbsStock = namedtuple(
    "Stock", "created title symbol qty price raw description idx")


class Stock(AbsStock, DbMixin):
    index = 0

    @ classmethod
    def make(cls, days_ago: int, size_factor: int, **kwargs) -> Stock:
        if not days_ago:
            days_ago = 1
        cls.index += 1

        def rnd_factor(): return int(size_factor * random.random() + 1)

        return cls(
            created=(datetime.now() - timedelta(days_ago % 200)).timestamp(),
            title=str_generator(20 * rnd_factor()),
            symbol=str_generator(3 * rnd_factor(), string.ascii_uppercase),
            qty=random.randint(1, 1000000),
            price=random.random() / days_ago,
            raw=randbytes(days_ago * rnd_factor()),
            description=str_generator(random.randint(
                size_factor * 10, 2 ** max(size_factor, 10))),
            idx=kwargs.get("idx", None) or cls.index,
        )

    @ classmethod
    def create(cls, cursor: sqlite3.Cursor, table: str, exec_: bool = True) -> str:
        super().create(cursor, table, exec_)
        query = f"""CREATE TABLE IF NOT EXISTS {table} (created real,
            title text, symbol text, qty real, price real, raw blob, description text, idx int unique);"""
        if exec:
            execute(cursor, query)
        return query


AbsHolder = namedtuple(
    "Holder", "name")


class Holder(AbsHolder, DbMixin):

    @ classmethod
    def create(cls, cursor: sqlite3.Cursor, table: str, exec_: bool = True) -> str:
        super().create(cursor, table, exec_)
        query = f"CREATE TABLE IF NOT EXISTS {table} (name text)"
        if exec:
            execute(cursor, query)
        return query


AbsTransaction = namedtuple(
    "Transaction", "d ts stock price qty description")


class Transaction(AbsTransaction, DbMixin):

    # python bug https://bugs.python.org/issue39679
    # def _register(self, cls, method=None):
    #     if hasattr(cls, '__func__'):
    #         setattr(cls, '__annotations__', cls.__func__.__annotations__)
    #         print(cls.__func__)
    #     return self.dispatcher.register(cls, func=method)
    # singledispatchmethod.register = _register

    @classmethod
    def create(cls, cursor: sqlite3.Cursor, table: str,
               foreign_key_deletion_strategy: str = 'NO ACTION', exec_: bool = True) -> str:
        super().create(cursor, table, exec_)
        query = f"""CREATE TABLE IF NOT EXISTS {table} (d DATE, ts timestamp , stock id NOT NULL REFERENCES stocks(idx)
            ON DELETE {foreign_key_deletion_strategy} , price REAL, qty INT, description TEXT)"""
        if exec:
            execute(cursor, query)
        return query

    # @singledispatchmethod
    @classmethod
    def make(cls, argument: int, stock_idx: int) -> Transaction:
        random.seed(time.process_time())
        return cls(
            d=date.today(),
            ts=datetime.utcnow(),
            stock=stock_idx,
            price=argument,
            qty=random.randint(100, 1000000),
            description=str_generator(random.randint(10, 1000)),
        )

    # @make.register(str) # https://bugs.python.org/issue39679
    # @classmethod
    # def _(cls, argument: str, stock_idx: int) -> Transaction:
    #     random.seed(time.process_time())
    #     return cls(
    #         d=bmnsqlite3.Date(2021, 10, 22),
    #         ts=bmnsqlite3.Timestamp(2021, 3, 22, 23, 9, 56, 900),
    #         stock=stock_idx,
    #         price=random.random(),
    #         qty=random.randint(100, 1000000),
    #         description=argument,
    #     )


class Point:

    def __init__(self, x: float = None, y: float = None) -> None:
        if (x or y) is None:
            x, y = random.random(), random.random()
        self.x, self.y = x, y

    def __conform__(self, protocol) -> Optional[str]:
        if protocol is bmnsqlite3.PrepareProtocol:
            return str(self)

    def __str__(self) -> str:
        return f"{self.x}:{self.y}"

    def __eq__(self, o: 'Point') -> bool:
        if isinstance(o, Point):
            return o.x == self.x and o.y == self.y
        raise TypeError(type(o))

    @ classmethod
    def test_adapter(cls, c: bmnsqlite3.Cursor, case: unittest.TestCase) -> None:
        p = cls()
        execute(c, "SELECT ?", (p,))
        case.assertEqual(c.fetchone()[0], str(p))

    @ staticmethod  # not an error !
    def adapt(cls) -> str:
        return str(cls)

    @ classmethod
    def convert(cls, data: bytes) -> Point:
        try:
            return cls(*[float(ch) for ch in data.split(b':')])
        except TypeError as te:
            log.error(f"{data} => {te}")
            raise
