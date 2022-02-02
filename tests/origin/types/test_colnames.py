# tests\origin\types\test_colnames.py
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


class ColNamesTests(BmnTestCase):
    def setUp(self):
        super().setUp()
        self.con = self._connect(detect_types=bmnsqlite3.PARSE_COLNAMES)
        self.cur = self.con.cursor()
        self.cur.execute("create table test(x foo)")

        bmnsqlite3.converters["FOO"] = lambda x: "[%s]" % x.decode("ascii")
        bmnsqlite3.converters["BAR"] = lambda x: "<%s>" % x.decode("ascii")
        bmnsqlite3.converters["EXC"] = lambda x: 5 / 0
        bmnsqlite3.converters["B1B1"] = lambda x: "MARKER"

    def tearDown(self):
        super().tearDown()
        del bmnsqlite3.converters["FOO"]
        del bmnsqlite3.converters["BAR"]
        del bmnsqlite3.converters["EXC"]
        del bmnsqlite3.converters["B1B1"]
        self.cur.close()
        self.con.close()

    def test_decl_type_not_used(self):
        """
        Assures that the declared type is not used when PARSE_DECLTYPES
        is not set.
        """
        self.cur.execute("insert into test(x) values (?)", ("xxx",))
        self.cur.execute("select x from test")
        val = self.cur.fetchone()[0]
        self.assertEqual(val, "xxx")

    def test_none(self):
        self.cur.execute("insert into test(x) values (?)", (None,))
        self.cur.execute("select x from test")
        val = self.cur.fetchone()[0]
        self.assertEqual(val, None)

    def test_col_name(self):
        self.cur.execute("insert into test(x) values (?)", ("xxx",))
        self.cur.execute('select x as "x y [bar]" from test')
        val = self.cur.fetchone()[0]
        self.assertEqual(val, "<xxx>")

        # Check if the stripping of colnames works. Everything after the first
        # '[' (and the preceding space) should be stripped.
        self.assertEqual(self.cur.description[0][0], "x y")

    def test_case_in_converter_name(self):
        self.cur.execute("select 'other' as \"x [b1b1]\"")
        val = self.cur.fetchone()[0]
        self.assertEqual(val, "MARKER")

    def test_cursor_description_no_row(self):
        """
        cursor.description should at least provide the column name(s), even if
        no row returned.
        """
        self.cur.execute("select * from test where 0 = 1")
        self.assertEqual(self.cur.description[0][0], "x")

    def test_cursor_description_insert(self):
        self.cur.execute("insert into test values (1)")
        self.assertIsNone(self.cur.description)
