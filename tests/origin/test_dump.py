# tests\origin\test_dump.py
# This file is part of bmnsqlite3.
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# original copyrights of code sourse:
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

from tests.origin import BmnTestCase


class DumpTests(BmnTestCase):
    def setUp(self):
        super().setUp()
        self.cx = self._connect(memory_table=False)
        self.cu = self.cx.cursor()

    def tearDown(self):
        super().tearDown()
        self.cu.close()
        self.cx.close()

    def test_table_dump(self):
        expected_sqls = [
            """CREATE TABLE "index"("index" blob);""",
            """INSERT INTO "index" VALUES(X'01');""",
            """CREATE TABLE "quoted""table"("quoted""field" text);""",
            """INSERT INTO "quoted""table" VALUES('quoted''value');""",
            "CREATE TABLE t1(id integer primary key, s1 text, "
            "t1_i1 integer not null, i2 integer, unique (s1), "
            "constraint t1_idx1 unique (i2));",
            "INSERT INTO \"t1\" VALUES(1,'foo',10,20);",
            "INSERT INTO \"t1\" VALUES(2,'foo2',30,30);",
            "CREATE TABLE t2(id integer, t2_i1 integer, "
            "t2_i2 integer, primary key (id),"
            "foreign key(t2_i1) references t1(t1_i1));",
            "CREATE TRIGGER trigger_1 update of t1_i1 on t1 "
            "begin "
            "update t2 set t2_i1 = new.t1_i1 where t2_i1 = old.t1_i1; "
            "end;",
            "CREATE VIEW v1 as select * from t1 left join t2 "
            "using (id);"
        ]
        [self.cu.execute(s) for s in expected_sqls]
        i = self.cx.iterdump()
        actual_sqls = [s for s in i]
        expected_sqls = ['BEGIN TRANSACTION;'] + expected_sqls + \
                        ['COMMIT;']
        [self.assertEqual(expected_sqls[i], actual_sqls[i])
         for i in range(len(expected_sqls))]

    def test_unorderable_row(self):
        # iterdump() should be able to cope with unorderable row types (issue #15545)
        class UnorderableRow:
            def __init__(self, _, row):
                self.row = row

            def __getitem__(self, index):
                return self.row[index]

        self.cx.row_factory = UnorderableRow
        create_alpha = """CREATE TABLE "alpha" ("one");"""
        create_beta = """CREATE TABLE "beta" ("two");"""
        expected = [
            "BEGIN TRANSACTION;",
            create_alpha,
            create_beta,
            "COMMIT;"
        ]
        self.cu.execute(create_beta)
        self.cu.execute(create_alpha)
        got = list(self.cx.iterdump())
        self.assertEqual(expected, got)