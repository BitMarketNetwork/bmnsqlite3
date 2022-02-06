#!/usr/bin/env python3
from __future__ import annotations

import glob
import re
import shlex
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.request import urlopen
from zipfile import ZipFile

if TYPE_CHECKING:
    from typing import Final, Sequence, Dict, Tuple

WORK_DIR: Final = Path(__file__).parent

CPYTHON_VERSION_LIST: Final = (
    (3, 7),
    (3, 8),
    (3, 9),
    (3, 10),
)
CPYTHON_DIR: Final = WORK_DIR / "cpython"
CPYTHON_VERSION_DIR: Final = WORK_DIR / "cpython-{}.{}"

SQLITE_VERSION: Final = (
    2022,
    3, 37, 2
)
SQLITE_URL: Final = (
        "https://www.sqlite.org/"
        + "{:d}/sqlite-amalgamation-{:d}{:02d}{:02d}00.zip"
)
SQLITE_DIR: Final = WORK_DIR / "sqlite"


def print_error_fatal(message: str):
    print(message, file=sys.stderr)
    exit(1)


def print_info(message: str):
    print(message)


def print_version_map(
        version_map: Dict[Tuple[int, ...], Tuple[Tuple[int, ...], bytes]]) \
        -> None:
    headers_row = (
        "Python version",
        "CPython tag",
        "SQLite version"
    )
    columns_width = [*map(len, headers_row)]

    rows = []
    for (version, (_, tag)) in sorted(version_map.items(), key=lambda k: k[0]):
        row = (
            ".".join(map(str, version)),
            tag.decode(),
            ".".join(map(str, SQLITE_VERSION[1:]))
        )
        for i in range(len(row)):
            if len(row[i]) > columns_width[i]:
                columns_width[i] = len(row[i])
        rows.append(row)

    # Markdown now
    output = "\n|"
    for i in range(len(headers_row)):
        output += " " + headers_row[i].ljust(columns_width[i]) + " |"

    output += "\n|"
    for i in range(len(headers_row)):
        output += ":" + "-" * (columns_width[i] + 2 - 1) + "|"

    for row in rows:
        output += "\n|"
        for i in range(len(row)):
            output += " " + row[i].ljust(columns_width[i]) + " |"

    print(output + "\n")


def git(
        *args: Sequence[str],
        capture_output: bool = False) -> subprocess.CompletedProcess:
    args = ("git", *args)
    print_info("RUN: " + " ".join(map(shlex.quote, args)))

    try:
        return subprocess.run(
            args,
            capture_output=capture_output,
            check=True)
    except FileNotFoundError:
        print_error_fatal("'git' executable not found.")


def cpython_git(
        *args: Sequence[str],
        capture_output: bool = False) -> subprocess.CompletedProcess:
    return git("-C", str(CPYTHON_DIR), *args, capture_output=capture_output)


def cpython_fetch() -> None:
    if not CPYTHON_DIR.exists():
        git(
            "clone",
            "https://github.com/python/cpython.git",
            str(CPYTHON_DIR))
    cpython_git("fetch", "--tags")


def cpython_create_version_map() \
        -> Dict[Tuple[int, ...], Tuple[Tuple[int, ...], bytes]]:
    version_map = dict()
    for tag in cpython_git(
            "tag",
            capture_output=True).stdout.split(b"\n"):
        m = re.match(r'^v(\d+)\.(\d+)\.(\d+)$', tag.decode())
        if not m:
            continue
        found_version = (int(m[1]), int(m[2]), int(m[3]))
        for version in CPYTHON_VERSION_LIST:
            if found_version[:len(version)] == version:
                if (
                        not version_map.get(version)
                        or version_map[version][0] < found_version
                ):
                    version_map[version] = (found_version, tag)
    return version_map


def cpython_copy(output_path: Path) -> None:
    def copy_verbose(src, dst, *, follow_symlinks=True) -> None:
        print_info(
            "COPY: "
            + str(Path(src).relative_to(WORK_DIR))
            + " -> "
            + str(Path(dst).relative_to(WORK_DIR)))
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)

    def copy_verbose_tests(src, dst, *, follow_symlinks=True) -> None:
        dst = Path(dst)
        if dst.match("*.py") and dst.name != "__init__.py":
            dst = dst.with_stem("test_" + dst.stem)
        return copy_verbose(src, dst, follow_symlinks=follow_symlinks)

    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir()

    shutil.copytree(
        CPYTHON_DIR / "Modules" / "_sqlite",
        output_path / "_sqlite",
        copy_function=copy_verbose)
    shutil.copytree(
        CPYTHON_DIR / "Lib" / "sqlite3" / "test",
        output_path / "test",
        copy_function=copy_verbose_tests)
    shutil.copytree(
        CPYTHON_DIR / "Lib" / "test" / "support",
        output_path / "test" / "test" / "support",
        copy_function=copy_verbose)
    open(output_path / "test" / "test" / "__init__.py", "w").close()

    for py_file in glob.iglob(
            "**/*.py",
            root_dir=output_path,
            recursive=True):
        with open(output_path / py_file, "rb") as f:
            s = f.read().replace(b"sqlite3", b"bmnsqlite3")
        with open(output_path / py_file, "wb") as f:
            f.write(s)
        del s


def sqlite_copy() -> None:
    if SQLITE_DIR.exists():
        shutil.rmtree(SQLITE_DIR)
    SQLITE_DIR.mkdir()

    url = SQLITE_URL.format(*SQLITE_VERSION)
    print_info("DOWNLOAD: " + url)

    with urlopen(url) as f:
        zip_file = BytesIO(f.read())
    with ZipFile(zip_file) as zip_file:
        for file_info in zip_file.infolist():
            if file_info.is_dir():
                continue
            output_file = PurePosixPath(file_info.filename)

            assert not output_file.is_absolute()
            assert len(output_file.parts) > 1

            output_file = SQLITE_DIR.joinpath(*output_file.parts[1:])
            print_info(
                "UNZIP: "
                + str(file_info.filename)
                + " -> "
                + str(Path(output_file).relative_to(WORK_DIR)))

            with zip_file.open(file_info.filename) as zf:
                with open(output_file, "wb") as f:
                    f.write(zf.read())
                    f.flush()


def main() -> int:
    git("version")

    cpython_fetch()
    version_map = cpython_create_version_map()
    for version, (_, tag) in version_map.items():
        cpython_git("checkout", "tags/" + tag.decode())
        print_info("CPYTHON: " + tag.decode())
        cpython_copy(
            CPYTHON_VERSION_DIR.with_name(
                CPYTHON_VERSION_DIR.name.format(*version)))

    sqlite_copy()

    print_version_map(version_map)
    print_info("CPython updated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
