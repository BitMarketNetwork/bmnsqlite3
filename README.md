# bmnsqlite3

SQLite3 Wrapper with VFS support.

# Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Development Version](#development-version)
- [SQLite Version Map](#sqlite-version-map)

# Requirements:

- Python >= 3.7, < 3.11

# Installation

```shell
$ python3 -m pip install bmnsqlite3
```

# Development Version

Depending on your installed environment, in the instructions below you will need
to use `python` instead of `python3`.

If you want to use the package in "Debug Mode", set the environment variable
`BMN_DEBUG=1` during package installation. For example:
`BMN_DEBUG=1 python3 -m pip install .`

- **Check out the code from GitHub, or download and extract tarball / ZIP
  archive**:

  ```shell
  $ git clone git://github.com/BitMarketNetwork/bmnslite3.git
  $ cd bmnslite3
  ```

- **Copy _sqlite/sqlite3 modules from CPython repository**:

  This tool automatically clones the CPython repository and copies the required
  files for each supported version of Python.

  ```shell
  $ python3 ./3rdparty/update.py
  ```

- **Install in editable mode ("develop mode")**:

  ```shell
  $ python3 -m pip install --user -e .[dev]
  ```

- **Normal installation (optional)**:

  ```shell
  $ python3 -m pip install --user .[dev]
  ```

- **Run tests**:

  ```shell
  $ python3 -m tox
  ```

- **Build sdist package**:

    ```shell
    $ python3 -m build --sdist
    ```

- **Build wheel package**:
    - Windows:

      ```shell
      $ python3 -m build --wheel
      ```

- **Upload to Test PyPI**:

  ```shell
  $ python3 -m twine upload --config-file ./.pypirc -r testpypi dist/*
  ```

# SQLite Version Map

| Python version | CPython tag | SQLite version |
|:---------------|:------------|:---------------|
| 3.10           | v3.10.2     | 3.37.2         |
| 3.7            | v3.7.12     | 3.37.2         |
| 3.8            | v3.8.12     | 3.37.2         |
| 3.9            | v3.9.10     | 3.37.2         |
