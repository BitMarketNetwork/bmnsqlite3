# tests\origin\dbapi2\test_extensions.py
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


class ExtensionTests(BmnTestCase):
    def test_script_string_sql(self):
        con = self._connect()
        cur = con.cursor()
        cur.executescript("""
            -- bla bla
            /* a stupid comment */
            create table a(i);
            insert into a(i) values (5);
            """)
        cur.execute("select i from a")
        res = cur.fetchone()[0]
        self.assertEqual(res, 5)

    def test_script_syntax_error(self):
        con = self._connect()
        cur = con.cursor()
        with self.assertRaises(bmnsqlite3.OperationalError):
            cur.executescript("create table test(x); asdf; create table test2(x)")

    def test_script_error_normal(self):
        con = self._connect()
        cur = con.cursor()
        with self.assertRaises(bmnsqlite3.OperationalError):
            cur.executescript("create table test(sadfsadfdsa); select foo from hurz;")

    def test_cursor_executescript_as_bytes(self):
        con = self._connect()
        cur = con.cursor()
        with self.assertRaises(ValueError) as cm:
            cur.executescript(b"create table test(foo); insert into test(foo) values (5);")
        self.assertEqual(str(cm.exception), 'script argument must be unicode.')

    def test_connection_execute(self):
        con = self._connect()
        result = con.execute("select 5").fetchone()[0]
        self.assertEqual(result, 5, "Basic test of Connection.execute")

    def test_connection_executemany(self):
        con = self._connect()
        con.execute("create table test(foo)")
        con.executemany("insert into test(foo) values (?)", [(3,), (4,)])
        result = con.execute("select foo from test order by foo").fetchall()
        self.assertEqual(result[0][0], 3, "Basic test of Connection.executemany")
        self.assertEqual(result[1][0], 4, "Basic test of Connection.executemany")

    def test_connection_executescript(self):
        con = self._connect()
        con.executescript("create table test(foo); insert into test(foo) values (5);")
        result = con.execute("select foo from test").fetchone()[0]
        self.assertEqual(result, 5, "Basic test of Connection.executescript")
