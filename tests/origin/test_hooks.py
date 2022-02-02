# tests\origin\test_hooks.py
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


import unittest

import bmnsqlite3
from tests.origin import BmnTestCase
from tests.origin.os_helper import TESTFN, unlink


class CollationTests(BmnTestCase):
    def test_create_collation_not_string(self):
        con = self._connect()
        with self.assertRaises(TypeError):
            con.create_collation(None, lambda x, y: (x > y) - (x < y))

    def test_create_collation_not_callable(self):
        con = self._connect()
        with self.assertRaises(TypeError) as cm:
            con.create_collation("X", 42)
        self.assertEqual(str(cm.exception), 'parameter must be callable')

    def test_create_collation_not_ascii(self):
        con = self._connect()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            con.create_collation("collä", lambda x, y: (x > y) - (x < y))

    def test_create_collation_bad_upper(self):
        class BadUpperStr(str):
            def upper(self):
                return None

        con = self._connect()

        def mycoll(x, y):
            return -((x > y) - (x < y))

        con.create_collation(BadUpperStr("mycoll"), mycoll)
        result = con.execute("""
            select x from (
            select 'a' as x
            union
            select 'b' as x
            ) order by x collate mycoll
            """).fetchall()
        self.assertEqual(result[0][0], 'b')
        self.assertEqual(result[1][0], 'a')

    def test_collation_is_used(self):
        def mycoll(x, y):
            # reverse order
            return -((x > y) - (x < y))

        con = self._connect()
        con.create_collation("mycoll", mycoll)
        sql = """
            select x from (
            select 'a' as x
            union
            select 'b' as x
            union
            select 'c' as x
            ) order by x collate mycoll
            """
        result = con.execute(sql).fetchall()
        self.assertEqual(result, [('c',), ('b',), ('a',)],
                         msg='the expected order was not returned')

        con.create_collation("mycoll", None)
        with self.assertRaises(bmnsqlite3.OperationalError) as cm:
            con.execute(sql).fetchall()
        self.assertEqual(str(cm.exception),
                         'no such collation sequence: mycoll')

    def test_collation_returns_large_integer(self):
        def mycoll(x, y):
            # reverse order
            return -((x > y) - (x < y)) * 2 ** 32

        con = self._connect()
        con.create_collation("mycoll", mycoll)
        sql = """
            select x from (
            select 'a' as x
            union
            select 'b' as x
            union
            select 'c' as x
            ) order by x collate mycoll
            """
        result = con.execute(sql).fetchall()
        self.assertEqual(result, [('c',), ('b',), ('a',)],
                         msg="the expected order was not returned")

    def test_collation_register_twice(self):
        """
        Register two different collation functions under the same name.
        Verify that the last one is actually used.
        """
        con = self._connect()
        con.create_collation("mycoll", lambda x, y: (x > y) - (x < y))
        con.create_collation("mycoll", lambda x, y: -((x > y) - (x < y)))
        result = con.execute("""
            select x from (select 'a' as x union select 'b' as x) order by x collate mycoll
            """).fetchall()
        self.assertEqual(result[0][0], 'b')
        self.assertEqual(result[1][0], 'a')

    def test_deregister_collation(self):
        """
        Register a collation, then deregister it. Make sure an error is raised if we try
        to use it.
        """
        con = self._connect()
        con.create_collation("mycoll", lambda x, y: (x > y) - (x < y))
        con.create_collation("mycoll", None)
        with self.assertRaises(bmnsqlite3.OperationalError) as cm:
            con.execute(
                "select 'a' as x union select 'b' as x order by x collate mycoll")
        self.assertEqual(str(cm.exception),
                         'no such collation sequence: mycoll')


class ProgressTests(BmnTestCase):
    def test_progress_handler_used(self):
        """
        Test that the progress handler is invoked once it is set.
        """
        con = self._connect()
        progress_calls = []

        def progress():
            progress_calls.append(None)
            return 0

        con.set_progress_handler(progress, 1)
        con.execute("""
            create table foo(a, b)
            """)
        self.assertTrue(progress_calls)

    def test_opcode_count(self):
        """
        Test that the opcode argument is respected.
        """
        con = self._connect()
        progress_calls = []

        def progress():
            progress_calls.append(None)
            return 0

        con.set_progress_handler(progress, 1)
        curs = con.cursor()
        curs.execute("""
            create table foo (a, b)
            """)
        first_count = len(progress_calls)
        progress_calls = []
        con.set_progress_handler(progress, 2)
        curs.execute("""
            create table bar (a, b)
            """)
        second_count = len(progress_calls)
        self.assertGreaterEqual(first_count, second_count)

    def test_cancel_operation(self):
        """
        Test that returning a non-zero value stops the operation in progress.
        """
        con = self._connect()

        def progress():
            return 1

        con.set_progress_handler(progress, 1)
        curs = con.cursor()
        self.assertRaises(
            bmnsqlite3.OperationalError,
            curs.execute,
            "create table bar (a, b)")

    def test_clear_handler(self):
        """
        Test that setting the progress handler to None clears the previously set handler.
        """
        con = self._connect()
        action = 0

        def progress():
            nonlocal action
            action = 1
            return 0

        con.set_progress_handler(progress, 1)
        con.set_progress_handler(None, 1)
        con.execute("select 1 union select 2 union select 3").fetchall()
        self.assertEqual(action, 0, "progress handler was not cleared")


class TraceCallbackTests(BmnTestCase):
    def test_trace_callback_used(self):
        """
        Test that the trace callback is invoked once it is set.
        """
        con = self._connect()
        traced_statements = []

        def trace(statement):
            traced_statements.append(statement)

        con.set_trace_callback(trace)
        con.execute("create table foo(a, b)")
        self.assertTrue(traced_statements)
        self.assertTrue(
            any("create table foo" in stmt for stmt in traced_statements))

    def test_clear_trace_callback(self):
        """
        Test that setting the trace callback to None clears the previously set callback.
        """
        con = self._connect()
        traced_statements = []

        def trace(statement):
            traced_statements.append(statement)

        con.set_trace_callback(trace)
        con.set_trace_callback(None)
        con.execute("create table foo(a, b)")
        self.assertFalse(traced_statements, "trace callback was not cleared")

    def test_unicode_content(self):
        """
        Test that the statement can contain unicode literals.
        """
        unicode_value = '\xf6\xe4\xfc\xd6\xc4\xdc\xdf\u20ac'
        con = self._connect()
        traced_statements = []

        def trace(statement):
            traced_statements.append(statement)

        con.set_trace_callback(trace)
        con.execute("create table foo(x)")
        con.execute('insert into foo(x) values ("%s")' % unicode_value)
        con.commit()
        self.assertTrue(any(unicode_value in stmt for stmt in traced_statements),
                        "Unicode data %s garbled in trace callback: %s"
                        % (ascii(unicode_value), ', '.join(map(ascii, traced_statements))))

    @unittest.skip("TODO")
    def test_trace_callback_content(self):
        # set_trace_callback() shouldn't produce duplicate content (bpo-26187)
        traced_statements = []

        def trace(statement):
            traced_statements.append(statement)

        queries = ["create table foo(x)",
                   "insert into foo(x) values(1)"]
        self.addCleanup(unlink, TESTFN)
        con1 = self._connect(TESTFN, erase_db=True, isolation_level=None)
        con2 = self._connect(TESTFN, erase_db=False, shift_wrapper=False)
        con1.set_trace_callback(trace)
        cur = con1.cursor()
        cur.execute(queries[0])
        # TODO: fails test sometimes ... hard to reproduce
        con2.execute("create table bar(x)")
        cur.execute(queries[1])
        self.assertEqual(traced_statements, queries)