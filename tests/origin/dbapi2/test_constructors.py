# tests\origin\dbapi2\test_constructors.py
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


class ConstructorTests(BmnTestCase):
    def test_date(self):
        bmnsqlite3.Date(2004, 10, 28)

    def test_time(self):
        bmnsqlite3.Time(12, 39, 35)

    def test_timestamp(self):
        bmnsqlite3.Timestamp(2004, 10, 28, 12, 39, 35)

    def test_date_from_ticks(self):
        bmnsqlite3.DateFromTicks(42)

    def test_time_from_ticks(self):
        bmnsqlite3.TimeFromTicks(42)

    def test_timestamp_from_ticks(self):
        bmnsqlite3.TimestampFromTicks(42)

    def test_binary(self):
        bmnsqlite3.Binary(b"\0'")
