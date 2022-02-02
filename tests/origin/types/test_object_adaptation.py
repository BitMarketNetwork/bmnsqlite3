# tests\origin\types\test_object_adaptation.py
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


class ObjectAdaptationTests(BmnTestCase):
    def cast(obj):
        return float(obj)

    cast = staticmethod(cast)

    def setUp(self):
        super().setUp()
        self.con = self._connect()
        # noinspection PyBroadException
        try:
            del bmnsqlite3.adapters[int]
        except:
            pass
        bmnsqlite3.register_adapter(int, ObjectAdaptationTests.cast)
        self.cur = self.con.cursor()

    def tearDown(self):
        super().tearDown()
        del bmnsqlite3.adapters[(int, bmnsqlite3.PrepareProtocol)]
        self.cur.close()
        self.con.close()

    def test_caster_is_used(self):
        self.cur.execute("select ?", (4,))
        val = self.cur.fetchone()[0]
        self.assertEqual(type(val), float)
