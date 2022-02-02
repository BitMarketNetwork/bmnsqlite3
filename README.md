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

| Python version | CPython version | SQLite version |
|----------------|-----------------|----------------|
| 3.7            | 3.7.0           | 3.21.0         |
| 3.8            | 3.8.2           | 3.28.0         |
| 3.9            | 3.9.2           | 3.32.3         |
| 3.10           | v3.10.0a6       | 3.34.0         |
