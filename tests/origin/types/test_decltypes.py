# tests\origin\types\test_decltypes.py
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


class DeclTypesTests(BmnTestCase):
    class Foo:
        def __init__(self, _val):
            if isinstance(_val, bytes):
                # sqlite3 always calls __init__ with a bytes created from a
                # UTF-8 string when __conform__ was used to store the object.
                _val = _val.decode('utf-8')
            self.val = _val

        def __eq__(self, other):
            if not isinstance(other, DeclTypesTests.Foo):
                return NotImplemented
            return self.val == other.val

        def __conform__(self, protocol):
            if protocol is bmnsqlite3.PrepareProtocol:
                return self.val
            else:
                return None

        def __str__(self):
            return "<%s>" % self.val

    class BadConform:
        def __init__(self, exc):
            self.exc = exc

        def __conform__(self, protocol):
            raise self.exc

    def setUp(self):
        super().setUp()
        self.con = self._connect(detect_types=bmnsqlite3.PARSE_DECLTYPES)
        self.cur = self.con.cursor()
        self.cur.execute("""
            create table test(
                i int,
                s str,
                f float,
                b bool,
                u unicode,
                foo foo,
                bin blob,
                n1 number,
                n2 number(5),
                bad bad,
                cbin cblob)
        """)

        # override float, make them always return the same number
        bmnsqlite3.converters["FLOAT"] = lambda x: 47.2

        # and implement two custom ones
        bmnsqlite3.converters["BOOL"] = lambda x: bool(int(x))
        bmnsqlite3.converters["FOO"] = DeclTypesTests.Foo
        bmnsqlite3.converters["BAD"] = DeclTypesTests.BadConform
        bmnsqlite3.converters["WRONG"] = lambda x: "WRONG"
        bmnsqlite3.converters["NUMBER"] = float
        bmnsqlite3.converters["CBLOB"] = lambda x: b"blobish"

    def tearDown(self):
        super().tearDown()
        del bmnsqlite3.converters["FLOAT"]
        del bmnsqlite3.converters["BOOL"]
        del bmnsqlite3.converters["FOO"]
        del bmnsqlite3.converters["BAD"]
        del bmnsqlite3.converters["WRONG"]
        del bmnsqlite3.converters["NUMBER"]
        del bmnsqlite3.converters["CBLOB"]
        self.cur.close()
        self.con.close()

    def test_string(self):
        # default
        self.cur.execute("insert into test(s) values (?)", ("foo",))
        self.cur.execute('select s as "s [WRONG]" from test')
        row = self.cur.fetchone()
        self.assertEqual(row[0], "foo")

    def test_small_int(self):
        # default
        self.cur.execute("insert into test(i) values (?)", (42,))
        self.cur.execute("select i from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], 42)

    def test_large_int(self):
        # default
        num = 2 ** 40
        self.cur.execute("insert into test(i) values (?)", (num,))
        self.cur.execute("select i from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], num)

    def test_float(self):
        # custom
        val = 3.14
        self.cur.execute("insert into test(f) values (?)", (val,))
        self.cur.execute("select f from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], 47.2)

    def test_bool(self):
        # custom
        self.cur.execute("insert into test(b) values (?)", (False,))
        self.cur.execute("select b from test")
        row = self.cur.fetchone()
        self.assertIs(row[0], False)

        self.cur.execute("delete from test")
        self.cur.execute("insert into test(b) values (?)", (True,))
        self.cur.execute("select b from test")
        row = self.cur.fetchone()
        self.assertIs(row[0], True)

    def test_unicode(self):
        # default
        val = "\xd6sterreich"
        self.cur.execute("insert into test(u) values (?)", (val,))
        self.cur.execute("select u from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], val)

    def test_foo(self):
        val = DeclTypesTests.Foo("bla")
        self.cur.execute("insert into test(foo) values (?)", (val,))
        self.cur.execute("select foo from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], val)

    @unittest.skip("TODO")
    def test_error_in_conform(self):
        val = DeclTypesTests.BadConform(TypeError)
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(bad) values (?)", (val,))
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(bad) values (:val)", {"val": val})

        val = DeclTypesTests.BadConform(KeyboardInterrupt)
        # with self.assertRaises(KeyboardInterrupt):
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(bad) values (?)", (val,))
        # with self.assertRaises(KeyboardInterrupt):
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(bad) values (:val)", {"val": val})

    def test_unsupported_seq(self):
        class Bar:
            pass

        val = Bar()
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(f) values (?)", (val,))

    def test_unsupported_dict(self):
        class Bar:
            pass

        val = Bar()
        with self.assertRaises(bmnsqlite3.InterfaceError):
            self.cur.execute("insert into test(f) values (:val)", {"val": val})

    def test_blob(self):
        # default
        sample = b"Guglhupf"
        val = memoryview(sample)
        self.cur.execute("insert into test(bin) values (?)", (val,))
        self.cur.execute("select bin from test")
        row = self.cur.fetchone()
        self.assertEqual(row[0], sample)

    def test_number1(self):
        self.cur.execute("insert into test(n1) values (5)")
        value = self.cur.execute("select n1 from test").fetchone()[0]
        # if the converter is not used, it's an int instead of a float
        self.assertEqual(type(value), float)

    def test_number2(self):
        """Checks whether converter names are cut off at '(' characters"""
        self.cur.execute("insert into test(n2) values (5)")
        value = self.cur.execute("select n2 from test").fetchone()[0]
        # if the converter is not used, it's an int instead of a float
        self.assertEqual(type(value), float)

    @unittest.skip("TODO")
    def test_convert_zero_sized_blob(self):
        self.con.execute("insert into test(cbin) values (?)", (b"",))
        cur = self.con.execute("select cbin from test")
        self.assertEqual(cur.fetchone()[0], b"blobish")
