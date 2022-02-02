from __future__ import annotations

import os
import site
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import setuptools
from setuptools.config import read_configuration

if TYPE_CHECKING:
    from typing import Final

# https://github.com/pypa/pip/issues/7953
if len(sys.argv) >= 3 and sys.argv[1] == "develop":
    site.ENABLE_USER_SITE = "--user" in sys.argv[2:]

PLATFORM_IS_WINDOWS: Final = sys.platform.startswith("win32")
PLATFORM_IS_DARWIN: Final = sys.platform.startswith("darwin")
PLATFORM_IS_LINUX: Final = sys.platform.startswith("linux")

# Paths
THIRD_PARTY_PATH: Final = \
    Path(".") \
    / "3rdparty" \
    / f"cpython-{sys.version_info.major}.{sys.version_info.minor}"
PYSQLITE3_PATH: Final = THIRD_PARTY_PATH / "_sqlite"
SQLITE3_PATH: Final = THIRD_PARTY_PATH / "sqlite"
SOURCE_PATH: Final = Path(".") / "src"

if not PYSQLITE3_PATH.exists():
    raise RuntimeError(
        "current version {}.{}.{} of the Python is not supported"
        .format(*sys.version_info[:3]))

# Other
METADATA: Final = read_configuration("setup.cfg")["metadata"]
PACKAGE_NAME: Final = METADATA["name"]
PACKAGE_VERSION: Final = METADATA["version"]
MODULE_NAME: Final = "_" + METADATA["name"]
DEBUG_MODE: Final = True if int(os.getenv("BMN_DEBUG", 0)) else False


def create_extension() -> setuptools.Extension:
    include_list = [str(THIRD_PARTY_PATH), str(SQLITE3_PATH)]
    quote = '\"' if PLATFORM_IS_WINDOWS else '"'

    source_list = [
        *PYSQLITE3_PATH.glob("*.c"),
        *SQLITE3_PATH.glob("*.c"),
        *SOURCE_PATH.glob("*.c")
    ]
    source_list = list(map(str, source_list))

    macros_list = [
        ("MODULE_NAME", quote + PACKAGE_NAME + quote),
        ("MODULE_VERSION", quote + PACKAGE_VERSION + quote),

        # https://www.sqlite.org/compile.html
        ("SQLITE_OMIT_LOAD_EXTENSION", "1")
    ]

    undef_macros_list = []

    if not DEBUG_MODE:
        macros_list += [
            ("NDEBUG", None)
        ]
    else:
        macros_list += [
            ("SQLITE_FORCE_OS_TRACE", "1"),
            ("SQLITE_HAVE_OS_TRACE", "1"),
            ("SQLITE_DEBUG_OS_TRACE", "1"),
        ]
        undef_macros_list += [
            "NDEBUG"
        ]

    link_args = []
    compile_args = []
    if PLATFORM_IS_WINDOWS:
        if not DEBUG_MODE:
            # TODO
            pass
        else:
            # TODO
            pass
    if PLATFORM_IS_DARWIN:
        if not DEBUG_MODE:
            # TODO
            pass
        else:
            # TODO
            pass
    if PLATFORM_IS_LINUX:
        if not DEBUG_MODE:
            link_args.append("-Wl,--strip-all,--discard-all")
        else:
            pass

    return setuptools.Extension(
        MODULE_NAME,
        source_list,
        py_limited_api=False,
        include_dirs=include_list,
        define_macros=macros_list,
        undef_macros=undef_macros_list,
        extra_compile_args=compile_args,
        extra_link_args=link_args
    )


setuptools.setup(
    packages=setuptools.find_packages(
        include=(
            PACKAGE_NAME,
            PACKAGE_NAME + ".*",
        )
    ),
    py_modules=[MODULE_NAME],
    ext_modules=[create_extension()]
)
