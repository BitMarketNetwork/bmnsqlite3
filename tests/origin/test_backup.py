# tests\origin\test_backup.py
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

import sys
import unittest
from unittest.case import skipIf

import bmnsqlite3
from tests.origin import BmnTestCase


class BackupTests(BmnTestCase):
    def setUp(self):
        super().setUp()
        cx = self.cx = self._connect()
        cx.execute('CREATE TABLE foo (key INTEGER)')
        cx.executemany('INSERT INTO foo (key) VALUES (?)', [(3,), (4,)])
        cx.commit()

    def tearDown(self):
        self.cx.close()

    def verify_backup(self, backup):
        result = backup.execute("SELECT key FROM foo ORDER BY key").fetchall()
        self.assertEqual(result[0][0], 3)
        self.assertEqual(result[1][0], 4)

    def test_bad_target(self):
        with self.assertRaises(TypeError):
            self.cx.backup(None)
        with self.assertRaises(TypeError):
            self.cx.backup()

    def test_bad_target_filename(self):
        with self.assertRaises(TypeError):
            self.cx.backup('some_file_name.db')

    def test_bad_target_same_connection(self):
        with self.assertRaises(ValueError):
            self.cx.backup(self.cx)

    def test_bad_target_closed_connection(self):
        self.cx.close()
        bck = self._connect()
        bck.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            self.cx.backup(bck)

    @skipIf(sys.version_info < (3, 9), "Python version must be 3.9 or higher")
    def test_bad_source_closed_connection(self):
        bck = self._connect(memory_table=True, shift_wrapper=False)
        source = self._connect(memory_table=True, shift_wrapper=False)
        source.close()
        with self.assertRaises(bmnsqlite3.ProgrammingError):
            source.backup(bck)

    @unittest.skip("TODO: python 3.8")
    def test_bad_target_in_transaction(self):
        self.cx.close()
        bck = self._connect()
        bck.execute('CREATE TABLE bar (key INTEGER)')
        bck.executemany('INSERT INTO bar (key) VALUES (?)', [(3,), (4,)])
        with self.assertRaises(bmnsqlite3.ProgrammingError) as cm:
            self.cx.backup(bck)
        if bmnsqlite3.sqlite_version_info < (3, 8, 8):
            self.assertEqual(str(cm.exception), 'target is in transaction')

    def test_keyword_only_args(self):
        with self.assertRaises(TypeError):
            with self._connect(shift_wrapper=False) as bck:
                self.cx.backup(bck, 1)

    def test_simple(self):
        with self._connect(shift_wrapper=False) as bck:
            self.cx.backup(bck)
            self.verify_backup(bck)

    def test_progress(self):
        journal = []

        def progress(status, _, __):
            journal.append(status)

        with self._connect(shift_wrapper=False) as bck:
            self.cx.backup(bck, pages=1, progress=progress)
            self.verify_backup(bck)

        self.assertEqual(len(journal), 2)
        self.assertEqual(journal[0], bmnsqlite3.SQLITE_OK)
        self.assertEqual(journal[1], bmnsqlite3.SQLITE_DONE)

    def test_progress_all_pages_at_once_1(self):
        journal = []

        def progress(_, remaining, __):
            journal.append(remaining)

        with self._connect(shift_wrapper=False) as bck:
            self.cx.backup(bck, progress=progress)
            self.verify_backup(bck)

        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0], 0)

    def test_progress_all_pages_at_once_2(self):
        journal = []

        def progress(_, remaining, __):
            journal.append(remaining)

        with self._connect(shift_wrapper=False) as bck:
            self.cx.backup(bck, pages=-1, progress=progress)
            self.verify_backup(bck)

        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0], 0)

    def test_non_callable_progress(self):
        with self.assertRaises(TypeError) as cm:
            with self._connect(shift_wrapper=False) as bck:
                self.cx.backup(bck, pages=1, progress='bar')
        self.assertEqual(str(cm.exception),
                         'progress argument must be a callable')

    @unittest.skip("TODO")
    def test_modifying_progress(self):
        journal = []

        def progress(_, remaining, __):
            if not journal:
                self.cx.execute(
                    'INSERT INTO foo (key) VALUES (?)', (remaining + 1000,))
                self.cx.commit()
            journal.append(remaining)

        with self._connect(shift_wrapper=False, erase_db=False) as bck:
            self.cx.backup(bck, pages=1, progress=progress)
            self.verify_backup(bck)

            result = bck.execute("SELECT key FROM foo"
                                 " WHERE key >= 1000"
                                 " ORDER BY key").fetchall()
            self.assertEqual(result[0][0], 1001)

        self.assertEqual(len(journal), 3)
        self.assertEqual(journal[0], 1)
        self.assertEqual(journal[1], 1)
        self.assertEqual(journal[2], 0)

    def test_failing_progress(self):
        def progress(*_):
            raise SystemError('nearly out of space')

        with self.assertRaises(SystemError) as err:
            with self._connect(shift_wrapper=False) as bck:
                self.cx.backup(bck, progress=progress)
        self.assertEqual(str(err.exception), 'nearly out of space')

    def test_database_source_name(self):
        with self._connect(memory_table=True, shift_wrapper=False) as bck:
            self.cx.backup(bck, name='main')
        with self._connect(memory_table=True, shift_wrapper=False) as bck:
            self.cx.backup(bck, name='temp')
        with self.assertRaises(bmnsqlite3.OperationalError) as cm:
            with self._connect(shift_wrapper=False) as bck:
                self.cx.backup(bck, name='non-existing')
        self.assertIn(
            str(cm.exception),
            ['SQL logic error', 'SQL logic error or missing database']
        )

        self.cx.execute("ATTACH DATABASE ':memory:' AS attached_db")
        self.cx.execute('CREATE TABLE attached_db.foo (key INTEGER)')
        self.cx.executemany(
            'INSERT INTO attached_db.foo (key) VALUES (?)', [(3,), (4,)])
        self.cx.commit()
        with self._connect(shift_wrapper=False, erase_db=False) as bck:
            self.cx.backup(bck, name='attached_db')
            self.verify_backup(bck)
