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

from aiohttp import ClientSession, ClientTimeout

DEFFILE = 'README.md'

DELS = set(string.punctuation) - {'_', '-'}
TRANSLATION = str.maketrans('', '', ''.join(DELS))

timeout = ClientTimeout(total=10)
queue: asyncio.Queue = asyncio.Queue()


def section_to_link(section: str) -> str:
    "Normalise a section name to a GitHub link"
    # This is based on
    # https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links
    # with some discovered modifications.
    text = section.strip().lower()
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.translate(TRANSLATION)

    return text


def check_file(
    file: Path, links: list[str], urls: dict[str, str], args: Namespace
) -> bool:
    "Check all links in given file"
    # Fetch sections and create unique links from them ..
    sections = set(
        s
        for p in re.findall(r'^#+\s+(.+)', file.read_text(), re.MULTILINE)
        if (s := section_to_link(p))
    )

    # Check links for this file ..
    all_ok = True
    basedir = file.parent
    for link in links:
        if (urlres := urls.get(link)) is not None:
            if args.verbose:
                verb = 'Skipping' if args.no_urls else 'Checking'
                print(f'{file}: {verb} URL "{link}" ..')

            if urlres:
                all_ok = False
                print(f'{file}: URL "{link}": {urlres}', file=sys.stderr)
        elif link[0] == '#':
            if args.verbose:
                print(f'{file}: Checking section link "{link}" ..')

            if link[1:] not in sections:
                all_ok = False
                print(
                    f'{file}: Link "{link}": does not match any section.',
                    file=sys.stderr,
                )
        else:
            if args.verbose:
                print(f'{file}: Checking path link "{link}" ..')

            if not (basedir / link).exists():
                all_ok = False
                print(f'{file}: Path "{link}": does not exist.', file=sys.stderr)

    return all_ok


async def check_url(urls: dict[str, str], session: ClientSession) -> None:
    "Async task to read URLs from queue and check each is valid and reachable"
    while True:
        try:
            url = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        try:
            async with session.get(url, timeout=timeout) as response:
                # Ignore forbidden links as browsers can sometimes access them
                if response.status != 403:
                    response.raise_for_status()
        except Exception as e:
            urls[url] = str(e)

        queue.task_done()


async def check_all_urls(urls: dict[str, str], max_parallel: int) -> None:
    async with ClientSession() as session:
        for url in urls:
            queue.put_nowait(url)

        n_tasks = min(len(urls), max_parallel)
        tasks = [asyncio.create_task(check_url(urls, session)) for _ in range(n_tasks)]
        await asyncio.gather(*tasks)


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


def get_file_links(file: Path) -> list[str]:
    "Extract all links from given file"
    text = file.read_text()

    # Fetch all inline links ..
    links = [find_link(lk) for lk in re.findall(r']\((.+)\)', text)]

    # Add all reference links ..
    links.extend(
        [lk.strip() for lk in re.findall(r'^\s*\[.+\]\s*:\s*(.+)', text, re.MULTILINE)]
    )

    # Return all unique links
    return list(dict.fromkeys(links))


async def main_async(args: Namespace) -> str | None:
    "Main async code"
    # Extract all links from all files
    links = {}
    for filestr in args.files or [DEFFILE]:
        # Only process each file once
        if (file := Path(filestr)) in links:
            continue

        if not file.is_file():
            return f'File "{file}" does not exist.'

        # Extract links from this file
        if filelinks := get_file_links(file):
            links[file] = filelinks

    # Get unique links across all files
    urls = {
        link: ''
        for file in links
        for link in links[file]
        if any(link.startswith(s) for s in ('http:', 'https:'))
    }

    # Validate all URLs
    if urls and not args.no_urls:
        await check_all_urls(urls, args.parallel_url_checks)

    had_error = False
    for file in links:
        if not check_file(file, links[file], urls, args):
            had_error = True

    return 'Errors found in file[s].' if had_error and not args.no_fail else None


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
