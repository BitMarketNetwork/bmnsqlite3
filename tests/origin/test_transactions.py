# tests\origin\test_transactions.py
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


import os
import unittest

import bmnsqlite3
from tests.origin import BmnTestCase
from tests.wrappers.testcases import get_db_path_str


def get_db_path_():
    return get_db_path_str("sqlite_test.db")


class TransactionTests(BmnTestCase):
    def setUp(self):
        super().setUp()
        try:
            os.remove(get_db_path_())
        except OSError:
            pass

        self.con1 = self._connect(
            db_filename=get_db_path_(), erase_db=False, timeout=0.1)
        self.cur1 = self.con1.cursor()

        self.con2 = self._connect(db_filename=get_db_path_(
        ), erase_db=False, shift_wrapper=False, timeout=0.1)
        self.cur2 = self.con2.cursor()

    def tearDown(self):
        super().tearDown()
        self.cur1.close()
        self.con1.close()
        self.cur2.close()
        self.con2.close()

    def test_dml_does_not_auto_commit_before(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.cur1.execute("create table test2(j)")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 0)

    def test_insert_starts_transaction(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 0)

    def test_update_starts_transaction(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.con1.commit()
        self.cur1.execute("update test set i=6")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchone()[0]
        self.assertEqual(res, 5)

    def test_delete_starts_transaction(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.con1.commit()
        self.cur1.execute("delete from test")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 1)

    def test_replace_starts_transaction(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.con1.commit()
        self.cur1.execute("replace into test(i) values (6)")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], 5)

    @unittest.skip("TODO")
    def test_toggle_auto_commit(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        self.con1.isolation_level = None
        self.assertEqual(self.con1.isolation_level, None)
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 1)

        self.con1.isolation_level = "DEFERRED"
        self.assertEqual(self.con1.isolation_level, "DEFERRED")
        self.cur1.execute("insert into test(i) values (5)")
        self.cur2.execute("select i from test")
        res = self.cur2.fetchall()
        self.assertEqual(len(res), 1)

    @unittest.skip("TODO")
    def test_raise_timeout(self):
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        with self.assertRaises(bmnsqlite3.OperationalError):
            self.cur2.execute("insert into test(i) values (5)")

    @unittest.skip("TODO")
    def test_locking(self):
        """
        This tests the improved concurrency with pysqlite 2.3.4. You needed
        to roll back con2 before you could commit con1.
        """
        self.cur1.execute("create table test(i)")
        self.cur1.execute("insert into test(i) values (5)")
        with self.assertRaises(bmnsqlite3.OperationalError):
            self.cur2.execute("insert into test(i) values (5)")
        # NO self.con2.rollback() HERE!!!
        self.con1.commit()

    def test_rollback_cursor_consistency(self):
        """
        Checks if cursors on the connection are set into a "reset" state
        when a rollback is done on the connection.
        """
        con = self._connect(shift_wrapper=False)
        cur = con.cursor()
        cur.execute("create table test(x)")
        cur.execute("insert into test(x) values (5)")
        cur.execute("select 1 union select 2 union select 3")

        con.rollback()
        with self.assertRaises(bmnsqlite3.InterfaceError):
            cur.fetchall()


class SpecialCommandTests(BmnTestCase):
    def setUp(self):
        super().setUp()
        self.con = self._connect()
        self.cur = self.con.cursor()

    def test_drop_table(self):
        self.cur.execute("create table test(i)")
        self.cur.execute("insert into test(i) values (5)")
        self.cur.execute("drop table test")

    def test_pragma(self):
        self.cur.execute("create table test(i)")
        self.cur.execute("insert into test(i) values (5)")
        self.cur.execute("pragma count_changes=1")

    def tearDown(self):
        super().tearDown()
        self.cur.close()
        self.con.close()


class TransactionalDDL(BmnTestCase):
    def setUp(self):
        super().setUp()
        self.con = self._connect()

    def test_ddl_does_not_autostart_transaction(self):
        # For backwards compatibility reasons, DDL statements should not
        # implicitly start a transaction.
        self.con.execute("create table test(i)")
        self.con.rollback()
        result = self.con.execute("select * from test").fetchall()
        self.assertEqual(result, [])

    def test_immediate_transactional_ddl(self):
        # You can achieve transactional DDL by issuing a BEGIN
        # statement manually.
        self.con.execute("begin immediate")
        self.con.execute("create table test(i)")
        self.con.rollback()
        with self.assertRaises(bmnsqlite3.OperationalError):
            self.con.execute("select * from test")

    def test_transactional_ddl(self):
        # You can achieve transactional DDL by issuing a BEGIN
        # statement manually.
        self.con.execute("begin")
        self.con.execute("create table test(i)")
        self.con.rollback()
        with self.assertRaises(bmnsqlite3.OperationalError):
            self.con.execute("select * from test")

    def tearDown(self):
        super().tearDown()
        self.con.close()
