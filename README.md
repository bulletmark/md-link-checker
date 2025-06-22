## MD-LINK-CHECKER - Utility to check url, section reference, and path links in Markdown files
[![PyPi](https://img.shields.io/pypi/v/md-link-checker)](https://pypi.org/project/md-link-checker/)

This is a simple command line utility to check url, section reference, and path
links in Markdown files. It iterates through the specified Markdown files and
checks each link in the file for validity. If no file is specified then it
defaults to checking `README.md` in the current directory. URL network fetches
can be slow so they are checked simultaneously, doing a maximum 10 in parallel
by default but you can change that using the `-p/--parallel-url-checks` option.
There are a number of similar utilities available so why did I create another
one? Well, all those that I tried didn't work!

E.g. check links in the `README.md` file in the current directory:

```
$ cd /path/to/my/project
$ md-link-checker
```

Check links in all the `README.md` files across your projects:

```
$ cd ..
$ md-link-checker */README.md
```

The latest version and documentation is available at
https://github.com/bulletmark/md-link-checker.


## Installation or Upgrade

Python 3.11 or later is required. You can run
[`md-link-checker`][md-link-checker] most easily using [`uvx`][uvx]. Just make
sure [`uv`][uv] is installed and then run the following command which will
install `md-link-checker` from [PyPi][md-link-checker-py] "on the fly" and will
then run it immediately:

```sh
$ uvx md-link-checker [myfile.md]
```

Or install [`md-link-checker`][md-link-checker] formally on your system using
using [`uv tool`][uvtool] (or [`pipx`][pipx] or [`pipxu`][pipxu]). To install:

```sh
$ uv tool install md-link-checker
```

To upgrade:

```sh
$ uv tool upgrade md-link-checker
```

To uninstall:

```sh
$ uv tool uninstall md-link-checker
```

## Command Line Options

Type `md-link-checker -h` to view the usage summary:

```
usage: md-link-checker [-h] [-u] [-p PARALLEL_URL_CHECKS] [-f] [-v]
                          [files ...]

Utility to check url, section reference, and path links in Markdown files.

positional arguments:
  files                 one or more markdown files to check, default =
                        "README.md"

options:
  -h, --help            show this help message and exit
  -u, --no-urls         do not check URL links, only check section and path
                        links
  -p, --parallel-url-checks PARALLEL_URL_CHECKS
                        max number of parallel URL checks to perform per file
                        (default=10)
  -f, --no-fail         do not return final error code after failures
  -v, --verbose         print links found in file as they are checked
```

## License

Copyright (C) 2025 Mark Blakeney. This program is distributed under the
terms of the GNU General Public License. This program is free software:
you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation,
either version 3 of the License, or any later version. This program is
distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License at
<http://www.gnu.org/licenses/> for more details.

[md-link-checker]: https://github.com/bulletmark/md-link-checker
[md-link-checker-py]: https://pypi.org/project/md-link-checker
[uv]: https://docs.astral.sh/uv/
[uvtool]: https://docs.astral.sh/uv/guides/tools/#using-tools
[uvx]: https://docs.astral.sh/uv/guides/tools/#using-tools
[pipx]: https://github.com/pypa/pipx
[pipxu]: https://github.com/bulletmark/pipxu

<!-- vim: se ai syn=markdown: -->
