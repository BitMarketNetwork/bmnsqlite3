# tests\origin\types\test_binary_converter.py
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

try:
    import zlib
except ImportError:
    zlib = None


@unittest.skipUnless(zlib, "requires zlib")
class BinaryConverterTests(BmnTestCase):
    def convert(s):
        return zlib.decompress(s)

    convert = staticmethod(convert)

    def setUp(self):
        super().setUp()
        self.con = self._connect(detect_types=bmnsqlite3.PARSE_COLNAMES)
        bmnsqlite3.register_converter("bin", BinaryConverterTests.convert)

    def tearDown(self):
        super().tearDown()
        self.con.close()

    def test_binary_input_for_converter(self):
        testdata = b"abcdefg" * 10
        result = self.con.execute('select ? as "x [bin]"', (memoryview(zlib.compress(testdata)),)).fetchone()[0]
        self.assertEqual(testdata, result)