# tests\origin\os_helper.py
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

import os
import sys
import time
import warnings

# Filename used for testing
if os.name == 'java':
    # Jython disallows @ in module names
    TESTFN_ASCII = '$test'
else:
    TESTFN_ASCII = '@test'

# Disambiguate TESTFN for parallel testing, while letting it remain a valid
# module name.
TESTFN_ASCII = "{}_{}_tmp".format(TESTFN_ASCII, os.getpid())

# TESTFN_UNICODE is a non-ascii filename
TESTFN_UNICODE = TESTFN_ASCII + "-\xe0\xf2\u0258\u0141\u011f"
if sys.platform == 'darwin':
    # In Mac OS X's VFS API file names are, by definition, canonically
    # decomposed Unicode, encoded using UTF-8. See QA1173:
    # http://developer.apple.com/mac/library/qa/qa2001/qa1173.html
    import unicodedata

    TESTFN_UNICODE = unicodedata.normalize('NFD', TESTFN_UNICODE)

# TESTFN_UNENCODABLE is a filename (str type) that should *not* be able to be
# encoded by the filesystem encoding (in strict mode). It can be None if we
# cannot generate such filename.
TESTFN_UNENCODABLE = None
if os.name == 'nt':
    # skip win32s (0) or Windows 9x/ME (1)
    if sys.getwindowsversion().platform >= 2:
        # Different kinds of characters from various languages to minimize the
        # probability that the whole name is encodable to MBCS (issue #9819)
        TESTFN_UNENCODABLE = TESTFN_ASCII + "-\u5171\u0141\u2661\u0363\uDC80"
        try:
            TESTFN_UNENCODABLE.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            pass
        else:
            print('WARNING: The filename %r CAN be encoded by the filesystem '
                  'encoding (%s). Unicode filename tests may not be effective'
                  % (TESTFN_UNENCODABLE, sys.getfilesystemencoding()))
            TESTFN_UNENCODABLE = None
# Mac OS X denies unencodable filenames (invalid utf-8)
elif sys.platform != 'darwin':
    try:
        # ascii and utf-8 cannot encode the byte 0xff
        b'\xff'.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError:
        # 0xff will be encoded using the surrogate character u+DCFF
        TESTFN_UNENCODABLE = TESTFN_ASCII \
                             + b'-\xff'.decode(sys.getfilesystemencoding(), 'surrogateescape')
    else:
        # File system encoding (eg. ISO-8859-* encodings) can encode
        # the byte 0xff. Skip some unicode filename tests.
        pass

# FS_NONASCII: non-ASCII character encodable by os.fsencode(),
# or an empty string if there is no such character.
FS_NONASCII = ''
for character in (
        # First try printable and common characters to have a readable filename.
        # For each character, the encoding list are just example of encodings able
        # to encode the character (the list is not exhaustive).

        # U+00E6 (Latin Small Letter Ae): cp1252, iso-8859-1
        '\u00E6',
        # U+0130 (Latin Capital Letter I With Dot Above): cp1254, iso8859_3
        '\u0130',
        # U+0141 (Latin Capital Letter L With Stroke): cp1250, cp1257
        '\u0141',
        # U+03C6 (Greek Small Letter Phi): cp1253
        '\u03C6',
        # U+041A (Cyrillic Capital Letter Ka): cp1251
        '\u041A',
        # U+05D0 (Hebrew Letter Alef): Encodable to cp424
        '\u05D0',
        # U+060C (Arabic Comma): cp864, cp1006, iso8859_6, mac_arabic
        '\u060C',
        # U+062A (Arabic Letter Teh): cp720
        '\u062A',
        # U+0E01 (Thai Character Ko Kai): cp874
        '\u0E01',

        # Then try more "special" characters. "special" because they may be
        # interpreted or displayed differently depending on the exact locale
        # encoding and the font.

        # U+00A0 (No-Break Space)
        '\u00A0',
        # U+20AC (Euro Sign)
        '\u20AC',
):
    try:
        # If Python is set up to use the legacy 'mbcs' in Windows,
        # 'replace' error mode is used, and encode() returns b'?'
        # for characters missing in the ANSI codepage
        if os.fsdecode(os.fsencode(character)) != character:
            raise UnicodeError
    except UnicodeError:
        pass
    else:
        FS_NONASCII = character
        break

# Save the initial cwd
SAVEDCWD = os.getcwd()

# TESTFN_UNDECODABLE is a filename (bytes type) that should *not* be able to be
# decoded from the filesystem encoding (in strict mode). It can be None if we
# cannot generate such filename (ex: the latin1 encoding can decode any byte
# sequence). On UNIX, TESTFN_UNDECODABLE can be decoded by os.fsdecode() thanks
# to the surrogateescape error handler (PEP 383), but not from the filesystem
# encoding in strict mode.
TESTFN_UNDECODABLE = None
for name in (
        # b'\xff' is not decodable by os.fsdecode() with code page 932. Windows
        # accepts it to create a file or a directory, or don't accept to enter to
        # such directory (when the bytes name is used). So test b'\xe7' first:
        # it is not decodable from cp932.
        b'\xe7w\xf0',
        # undecodable from ASCII, UTF-8
        b'\xff',
        # undecodable from iso8859-3, iso8859-6, iso8859-7, cp424, iso8859-8, cp856
        # and cp857
        b'\xae\xd5'
        # undecodable from UTF-8 (UNIX and Mac OS X)
        b'\xed\xb2\x80', b'\xed\xb4\x80',
        # undecodable from shift_jis, cp869, cp874, cp932, cp1250, cp1251, cp1252,
        # cp1253, cp1254, cp1255, cp1257, cp1258
        b'\x81\x98',
):
    try:
        name.decode(sys.getfilesystemencoding())
    except UnicodeDecodeError:
        TESTFN_UNDECODABLE = os.fsencode(TESTFN_ASCII) + name
        break

if FS_NONASCII:
    TESTFN_NONASCII = TESTFN_ASCII + FS_NONASCII
else:
    TESTFN_NONASCII = None
TESTFN = TESTFN_NONASCII or TESTFN_ASCII


def unlink(filename):
    try:
        _unlink(filename)
    except (FileNotFoundError, NotADirectoryError):
        pass


if sys.platform.startswith("win"):
    def _waitfor(func, pathname, waitall=False):
        # Perform the operation
        func(pathname)
        name = None
        # Now setup the wait loop
        if waitall:
            dirname = pathname
        else:
            dirname, name = os.path.split(pathname)
            dirname = dirname or '.'
        # Check for `pathname` to be removed from the filesystem.
        # The exponential backoff of the timeout amounts to a total
        # of ~1 second after which the deletion is probably an error
        # anyway.
        # Testing on an i7@4.3GHz shows that usually only 1 iteration is
        # required when contention occurs.
        timeout = 0.001
        while timeout < 1.0:
            # Note we are only testing for the existence of the file(s) in
            # the contents of the directory regardless of any security or
            # access rights.  If we have made it this far, we have sufficient
            # permissions to do that much using Python's equivalent of the
            # Windows API FindFirstFile.
            # Other Windows APIs can fail or give incorrect results when
            # dealing with files that are pending deletion.
            ll = os.listdir(dirname)
            if not (ll if waitall else name in ll):
                return
            # Increase the timeout and try again
            time.sleep(timeout)
            timeout *= 2
        warnings.warn('tests may fail, delete still pending for ' + pathname,
                      RuntimeWarning, stacklevel=4)


    def _unlink(filename):
        _waitfor(os.unlink, filename)
else:
    _unlink = os.unlink
