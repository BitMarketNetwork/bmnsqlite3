# tests\origin\dbapi2\test_connections.py
# This file is part of bmnsqlite3.
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# original copyrights of code source:
#
# Copyright (C) 2004-2005 Gerhard Häring <gh@ghaering.de>
#
# This file is part of pysqlite.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.



import bmnsqlite3
from tests.origin import BmnTestCase
from tests.origin.os_helper import TESTFN, unlink


class ConnectionTests(BmnTestCase):

    def setUp(self):
        super().setUp()
        self.cx = self._connect(memory_table=True)
        cu = self.cx.cursor()
        cu.execute("create table test(id integer primary key, name text)")
        cu.execute("insert into test(name) values (?)", ("foo",))

    def tearDown(self):
        self.cx.close()

    def test_commit(self):
        self.cx.commit()

    def test_commit_after_no_changes(self):
        """
        A commit should also work when no changes were made to the database.
        """
        self.cx.commit()
        self.cx.commit()

    def test_rollback(self):
        self.cx.rollback()

    def test_rollback_after_no_changes(self):
        """
        A rollback should also work when no changes were made to the database.
        """
        self.cx.rollback()
        self.cx.rollback()

    def test_cursor(self):
        self.cx.cursor()

    def test_failed_open(self):
        you_cannot_open_this = "/foo/bar/bla/23534/mydb.db"
        with self.assertRaises(bmnsqlite3.OperationalError):
            self._connect(you_cannot_open_this)

    def test_close(self):
        self.cx.close()

    def test_exceptions(self):
        # Optional DB-API extension.
        self.assertEqual(self.cx.Warning, bmnsqlite3.Warning)
        self.assertEqual(self.cx.Error, bmnsqlite3.Error)
        self.assertEqual(self.cx.InterfaceError, bmnsqlite3.InterfaceError)
        self.assertEqual(self.cx.DatabaseError, bmnsqlite3.DatabaseError)
        self.assertEqual(self.cx.DataError, bmnsqlite3.DataError)
        self.assertEqual(self.cx.OperationalError, bmnsqlite3.OperationalError)
        self.assertEqual(self.cx.IntegrityError, bmnsqlite3.IntegrityError)
        self.assertEqual(self.cx.InternalError, bmnsqlite3.InternalError)
        self.assertEqual(self.cx.ProgrammingError, bmnsqlite3.ProgrammingError)
        self.assertEqual(self.cx.NotSupportedError,
                         bmnsqlite3.NotSupportedError)

    def test_in_transaction(self):
        # Can't use db from setUp because we want to test initial state.
        cx = bmnsqlite3.connect(":memory:")
        cu = cx.cursor()
        self.assertEqual(cx.in_transaction, False)
        cu.execute(
            "create table transactiontest(id integer primary key, name text)")
        self.assertEqual(cx.in_transaction, False)
        cu.execute("insert into transactiontest(name) values (?)", ("foo",))
        self.assertEqual(cx.in_transaction, True)
        cu.execute("select name from transactiontest where name=?", ["foo"])
        cu.fetchone()
        self.assertEqual(cx.in_transaction, True)
        cx.commit()
        self.assertEqual(cx.in_transaction, False)
        cu.execute("select name from transactiontest where name=?", ["foo"])
        cu.fetchone()
        self.assertEqual(cx.in_transaction, False)

    def test_in_transaction_ro(self):
        with self.assertRaises(AttributeError):
            self.cx.in_transaction = True

    def test_open_with_path_like_object(self):
        """ Checks that we can successfully connect to a database using an object that
            is PathLike, i.e. has __fspath__(). """
        self.addCleanup(unlink, TESTFN)

        class Path:
            def __fspath__(self):
                return TESTFN

        path = Path()
        with bmnsqlite3.connect(path) as cx:
            cx.execute('create table test(id integer)')

    def test_open_uri(self):
        self.addCleanup(unlink, TESTFN)
        with bmnsqlite3.connect(TESTFN) as cx:
            cx.execute('create table test(id integer)')
        with bmnsqlite3.connect('file:' + TESTFN, uri=True) as cx:
            cx.execute('insert into test(id) values(0)')
        with bmnsqlite3.connect('file:' + TESTFN + '?mode=ro', uri=True) as cx:
            with self.assertRaises(bmnsqlite3.OperationalError):
                cx.execute('insert into test(id) values(1)')


class ClosedConTests(BmnTestCase):

    def test_closed_con_cursor(self):
        con = self._connect(memory_table=True)
        con.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.cursor()

    def test_closed_con_commit(self):
        con = self._connect()
        con.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.commit()

    def test_closed_con_rollback(self):
        con = self._connect()
        con.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.rollback()

    def test_closed_cur_execute(self):
        con = self._connect()
        cur = con.cursor()
        con.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            cur.execute("select 4")

    def test_closed_create_function(self):
        con = self._connect()
        con.close()

        def f(_): return 17

        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.create_function("foo", 1, f)

    def test_closed_create_aggregate(self):
        con = self._connect()
        con.close()

        class Agg:
            def __init__(self):
                pass

            def step(self, x):
                pass

            def finalize(self):
                return 17

        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.create_aggregate("foo", 1, Agg)

    def test_closed_set_authorizer(self):
        con = self._connect(memory_table=True)
        con.close()

        def authorizer(*_):
            return bmnsqlite3.DENY

        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.set_authorizer(authorizer)

    def test_closed_set_progress_callback(self):
        con = self._connect()
        con.close()

        def progress(): pass

        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.set_progress_handler(progress, 100)

    def test_closed_call(self):
        con = self._connect()
        con.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con()
