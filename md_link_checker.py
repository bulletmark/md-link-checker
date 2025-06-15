#!/usr/bin/env python3
"""
Utility to check url, section reference, and path links in Markdown files.
"""

# Author: Mark Blakeney, May 2019.
from __future__ import annotations

import re
import string
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

import requests  # type: ignore[import]

DEFFILE = 'README.md'

DELS = set(string.punctuation) - {'_', '-'}
TRANSLATION = str.maketrans('', '', ''.join(DELS))


def find_link(link: str) -> str:
    "Return a link from a markdown link text, ensure matching on final bracket"
    stack = 1
    for n, c in enumerate(link):
        if c == '(':
            stack += 1
        elif c == ')':
            stack -= 1
            if stack <= 0:
                return link[:n]

    return link


def make_link(section: str) -> str:
    "Normalise a section name to a GitHub link"
    # This is based on
    # https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links
    # with some discovered modifications.
    text = section.strip().lower()
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.translate(TRANSLATION)

    return text


def check_file(file: Path, args: Namespace) -> bool:
    "Check links in this file"
    ok = True
    text = file.read_text()

    # Fetch all inline links ..
    links = [find_link(lk) for lk in re.findall(r']\((.+)\)', text)]

    # Add all reference links ..
    links.extend(
        lk.strip() for lk in re.findall(r'^\s*\[.+\]\s*:\s*(.+)', text, re.MULTILINE)
    )

    # Fetch sections and create links from them ..
    sections = set(
        s for p in re.findall(r'^#+\s+(.+)', text, re.MULTILINE) if (s := make_link(p))
    )

    done = set()

    # Check url links ..
    for link in links:
        if any(link.startswith(s) for s in ('http:', 'https:')) and link not in done:
            done.add(link)
            if args.no_urls:
                if args.verbose:
                    print(f'{file}: Skipping URL link "{link}" ..')
            else:
                if args.verbose:
                    print(f'{file}: Checking URL link "{link}" ..')

                try:
                    r = requests.get(link, timeout=10)

                    # Ignore forbidden links as browsers can sometimes access them
                    if r.status_code != 403:
                        r.raise_for_status()

                except Exception as e:
                    ok = False
                    print(f'{file}: URL "{link}" : {e}.', file=sys.stderr)

    # Check section links ..
    for link in links:
        if link[0] == '#' and link not in done:
            done.add(link)
            if args.verbose:
                print(f'{file}: Checking section link "{link}" ..')

            if link[1:] not in sections:
                ok = False
                print(
                    f'{file}: Link "{link}": does not match any section.',
                    file=sys.stderr,
                )

    base = file.parent

    # Check path links ..
    for link in links:
        if link not in done:
            done.add(link)
            if args.verbose:
                print(f'{file}: Checking path link "{link}" ..')

            if not (base / link).exists():
                ok = False
                print(f'{file}: Path "{link}": does not exist.', file=sys.stderr)

    return ok


def main() -> str | None:
    "Main code"
    # Process command line options
    opt = ArgumentParser(description=__doc__)
    opt.add_argument(
        '-u',
        '--no-urls',
        action='store_true',
        help='do not check URL links, only check section and path links',
    )
    opt.add_argument(
        '-f',
        '--no-fail',
        action='store_true',
        help='do not return final error code after failures',
    )
    opt.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='print links found in file as they are checked',
    )
    opt.add_argument(
        'files',
        nargs='*',
        help=f'one or more markdown files to check, default = "{DEFFILE}"',
    )

    args = opt.parse_args()

    # Check each file on the command line
    error = False
    for file in args.files or [DEFFILE]:
        path = Path(file)
        if not path.exists():
            return f'File "{file}" does not exist.'

        if not check_file(Path(file), args):
            error = True

    return 'Errors found in file[s].' if error and not args.no_fail else None


if __name__ == '__main__':
    sys.exit(main())
