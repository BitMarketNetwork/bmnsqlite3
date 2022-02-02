# tests\origin\dbapi2\test_conflicts.py
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


class SqliteOnConflictTests(BmnTestCase):
    """
    Tests for SQLite's "insert on conflict" feature.

    See https://www.bmnsqlite3.org/lang_conflict.html for details.
    """

    def setUp(self):
        super().setUp()
        self.cx = self._connect()
        self.cu = self.cx.cursor()
        self.cu.execute("""
          CREATE TABLE test(
            id INTEGER PRIMARY KEY, name TEXT, unique_name TEXT UNIQUE
          );
        """)

    def tearDown(self):
        self.cu.close()
        self.cx.close()

    def test_on_conflict_rollback_with_explicit_transaction(self):
        self.cx.isolation_level = None  # autocommit mode
        self.cu = self.cx.cursor()
        # Start an explicit transaction.
        self.cu.execute("BEGIN")
        self.cu.execute("INSERT INTO test(name) VALUES ('abort_test')")
        self.cu.execute("INSERT OR ROLLBACK INTO test(unique_name) VALUES ('foo')")
        with self.assertRaises(bmnsqlite3.IntegrityError):
            self.cu.execute("INSERT OR ROLLBACK INTO test(unique_name) VALUES ('foo')")
        # Use connection to commit.
        self.cx.commit()
        self.cu.execute("SELECT name, unique_name from test")
        # Transaction should have rolled back and nothing should be in table.
        self.assertEqual(self.cu.fetchall(), [])

    def test_on_conflict_abort_raises_with_explicit_transactions(self):
        # Abort cancels the current sql statement but doesn't change anything
        # about the current transaction.
        self.cx.isolation_level = None  # autocommit mode
        self.cu = self.cx.cursor()
        # Start an explicit transaction.
        self.cu.execute("BEGIN")
        self.cu.execute("INSERT INTO test(name) VALUES ('abort_test')")
        self.cu.execute("INSERT OR ABORT INTO test(unique_name) VALUES ('foo')")
        with self.assertRaises(bmnsqlite3.IntegrityError):
            self.cu.execute("INSERT OR ABORT INTO test(unique_name) VALUES ('foo')")
        self.cx.commit()
        self.cu.execute("SELECT name, unique_name FROM test")
        # Expect the first two inserts to work, third to do nothing.
        self.assertEqual(self.cu.fetchall(), [('abort_test', None), (None, 'foo',)])

    def test_on_conflict_rollback_without_transaction(self):
        # Start of implicit transaction
        self.cu.execute("INSERT INTO test(name) VALUES ('abort_test')")
        self.cu.execute("INSERT OR ROLLBACK INTO test(unique_name) VALUES ('foo')")
        with self.assertRaises(bmnsqlite3.IntegrityError):
            self.cu.execute("INSERT OR ROLLBACK INTO test(unique_name) VALUES ('foo')")
        self.cu.execute("SELECT name, unique_name FROM test")
        # Implicit transaction is rolled back on error.
        self.assertEqual(self.cu.fetchall(), [])

    def test_on_conflict_abort_raises_without_transactions(self):
        # Abort cancels the current sql statement but doesn't change anything
        # about the current transaction.
        self.cu.execute("INSERT INTO test(name) VALUES ('abort_test')")
        self.cu.execute("INSERT OR ABORT INTO test(unique_name) VALUES ('foo')")
        with self.assertRaises(bmnsqlite3.IntegrityError):
            self.cu.execute("INSERT OR ABORT INTO test(unique_name) VALUES ('foo')")
        # Make sure all other values were inserted.
        self.cu.execute("SELECT name, unique_name FROM test")
        self.assertEqual(self.cu.fetchall(), [('abort_test', None), (None, 'foo',)])

    def test_on_conflict_fail(self):
        self.cu.execute("INSERT OR FAIL INTO test(unique_name) VALUES ('foo')")
        with self.assertRaises(bmnsqlite3.IntegrityError):
            self.cu.execute("INSERT OR FAIL INTO test(unique_name) VALUES ('foo')")
        self.assertEqual(self.cu.fetchall(), [])

    def test_on_conflict_ignore(self):
        self.cu.execute("INSERT OR IGNORE INTO test(unique_name) VALUES ('foo')")
        # Nothing should happen.
        self.cu.execute("INSERT OR IGNORE INTO test(unique_name) VALUES ('foo')")
        self.cu.execute("SELECT unique_name FROM test")
        self.assertEqual(self.cu.fetchall(), [('foo',)])

    def test_on_conflict_replace(self):
        self.cu.execute("INSERT OR REPLACE INTO test(name, unique_name) VALUES ('Data!', 'foo')")
        # There shouldn't be an IntegrityError exception.
        self.cu.execute("INSERT OR REPLACE INTO test(name, unique_name) VALUES ('Very different data!', 'foo')")
        self.cu.execute("SELECT name, unique_name FROM test")
        self.assertEqual(self.cu.fetchall(), [('Very different data!', 'foo')])
