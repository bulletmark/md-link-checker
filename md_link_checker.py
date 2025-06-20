#!/usr/bin/env python3
"""
Utility to check url, section reference, and path links in Markdown files.
"""

# Author: Mark Blakeney, May 2019.
from __future__ import annotations

import asyncio
import re
import string
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from aiohttp import ClientSession

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


async def check_url(queue: asyncio.Queue) -> bool:
    "Async task to read URLs from queue and check each is valid and reachable"
    all_ok = True
    while True:
        try:
            file, url, session, verbose = queue.get_nowait()
        except asyncio.QueueEmpty:
            return all_ok

        if verbose:
            print(f'{file}: Checking URL link "{url}" ..')

        try:
            async with session.get(url, timeout=10) as response:
                # Ignore forbidden links as browsers can sometimes access them
                if response.status != 403:
                    response.raise_for_status()
        except Exception as e:
            print(f'{file}: URL "{url}" : {e}.', file=sys.stderr)
            all_ok = False

        queue.task_done()


async def check_file(file: Path, args: Namespace, session: ClientSession) -> bool:
    "Check links in given file"
    text = file.read_text()

    # Fetch all unique inline links ..
    links = [find_link(lk) for lk in re.findall(r']\((.+)\)', text)]

    # Add all unique reference links ..
    links.extend(
        [lk.strip() for lk in re.findall(r'^\s*\[.+\]\s*:\s*(.+)', text, re.MULTILINE)]
    )

    # Fetch sections and create unique links from them ..
    sections = set(
        s for p in re.findall(r'^#+\s+(.+)', text, re.MULTILINE) if (s := make_link(p))
    )

    all_ok = True
    done = set()

    # Check URL links for this file ..
    queue: asyncio.Queue = asyncio.Queue()
    for link in links:
        if any(link.startswith(s) for s in ('http:', 'https:')) and link not in done:
            done.add(link)
            if args.no_urls:
                if args.verbose:
                    print(f'{file}: Skipping URL link "{link}" ..')
            else:
                queue.put_nowait((file, link, session, args.verbose))

    n_tasks = min(queue.qsize(), args.parallel_url_checks)
    tasks = [asyncio.create_task(check_url(queue)) for _ in range(n_tasks)]
    if not all(await asyncio.gather(*tasks)):
        all_ok = False

    # Check section links for this file ..
    for link in links:
        if link[0] == '#' and link not in done:
            done.add(link)
            if args.verbose:
                print(f'{file}: Checking section link "{link}" ..')

            if link[1:] not in sections:
                all_ok = False
                print(
                    f'{file}: Link "{link}": does not match any section.',
                    file=sys.stderr,
                )

    # Check path links for this file ..
    basedir = file.parent
    for link in links:
        if link not in done:
            done.add(link)
            if args.verbose:
                print(f'{file}: Checking path link "{link}" ..')

            if not (basedir / link).exists():
                all_ok = False
                print(f'{file}: Path "{link}": does not exist.', file=sys.stderr)

    return all_ok


async def main_async(args: Namespace) -> str | None:
    "Main async code"
    error = False
    async with ClientSession() as session:
        for file in args.files or [DEFFILE]:
            path = Path(file)
            if not path.is_file():
                return f'File "{path}" does not exist.'

            if not await check_file(path, args, session):
                error = True

    return 'Errors found in file[s].' if error and not args.no_fail else None


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
        '-p',
        '--parallel-url-checks',
        type=int,
        default=10,
        help='max number of parallel URL checks to perform per file (default=%(default)d)',
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

    return asyncio.run(main_async(opt.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
