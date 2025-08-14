#!/usr/bin/env python3
"""
Utility to check url, section reference, and path links in Markdown files.
"""

# Author: Mark Blakeney, Jun 2025
from __future__ import annotations

import asyncio
import re
import string
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

DEFFILE = 'README.md'
DELS = set(string.punctuation) - {'_', '-'}
TRANSLATION = str.maketrans('', '', ''.join(DELS))


def find_link(link: str) -> str:
    "Return a link from a markdown link text, finish on matching close bracket"
    stack = 1
    for n, c in enumerate(link):
        if c == '(':
            stack += 1
        elif c == ')':
            stack -= 1
            if stack <= 0:
                link = link[:n].strip()
                break

    # Remove any trailing title text
    return re.sub(r'\s+".+"$', '', link).strip()


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


def remove_code(text: str) -> str:
    "Remove code blocks and indented code from Markdown text"
    keep = True
    lines = []
    for ln in text.splitlines():
        if re.match(r'\s*```', ln):
            keep = not keep

        if keep and not re.match(r'\s{4}', ln):
            lines.append(ln)

    return '\n'.join(lines)


class File:
    "Class to represent each Markdown file"

    urls: dict[str, str] = {}
    urls_ignore: dict[str, str] = {}
    queue: asyncio.Queue = asyncio.Queue()
    timeout = ClientTimeout(total=10)

    def __init__(self, file: Path) -> None:
        "Constructor to read file and extract links"
        self.file = file
        text = remove_code(file.read_text())

        # Fetch all inline links with titles ..
        self.links = [find_link(lk) for lk in re.findall(r']\(([^\[\]]+)\)', text)]

        # Fetch all explicit links in angle brackets ..
        self.links.extend(re.findall(r'<(https*://[^>]+)>', text))

        # Build dict for any reference table
        ref_tags = {
            tag.strip().lower(): ref.strip()
            for tag, ref in re.findall(
                r'^\s*\[([^\]]+)\]\s*:\s*(.+)\s*', text, re.MULTILINE
            )
        }

        ## Add reference links to the links list and record the tags
        self.links.extend(ref_tags.values())
        self.ref_tags = set(ref_tags)

        # Remove duplicates from links, preserving order
        self.links = list(dict.fromkeys(self.links))

        # Save reference links, removing duplicates
        self.refs = list(
            dict.fromkeys(re.findall(r'\[[^\]]+\]\[([^\]]+)\]', text, re.MULTILINE))
        )

        # Save unique url links across all files
        self.urls.update(
            {u: '' for u in self.links if u.startswith(('http:', 'https:'))}
        )

        # Fetch sections and create unique links from them ..
        self.sections = set(
            s
            for p in re.findall(r'^#+\s+(.+)\s*', text, re.MULTILINE)
            if (s := section_to_link(p))
        )

    def check_ok(self, args: Namespace) -> bool:
        "Check and report all links in this file"
        all_ok = True
        basedir = self.file.parent
        for link in self.links:
            if (urlres := self.urls.get(link)) is not None:
                if args.verbose:
                    verb = 'Skipping' if args.no_urls else 'Checking'
                    print(f'{self.file}: - {verb} URL "{link}" ..')

                if urlres:
                    all_ok = False
                    print(f'{self.file}: URL "{link}": {urlres}', file=sys.stderr)
                elif (urlres := self.urls_ignore.get(link)) and not args.no_warnings:
                    print(
                        f'{self.file}: ignoring URL "{link}": {urlres}', file=sys.stderr
                    )
            elif link[0] == '#':
                if args.verbose:
                    print(f'{self.file}: - Checking section link "{link}" ..')

                if link[1:] not in self.sections:
                    all_ok = False
                    print(
                        f'{self.file}: Link "{link}": does not match any section.',
                        file=sys.stderr,
                    )
            else:
                if args.verbose:
                    print(f'{self.file}: - Checking path link "{link}" ..')

                if not (basedir / link).exists():
                    all_ok = False
                    print(
                        f'{self.file}: Path "{link}": does not exist.', file=sys.stderr
                    )

        for link in self.refs:
            if args.verbose:
                print(f'{self.file}: - Checking reference "{link}" ..')

            if link.lower() not in self.ref_tags:
                all_ok = False
                print(
                    f'{self.file}: Reference "{link}": does not match any tag.',
                    file=sys.stderr,
                )

        return all_ok

    @classmethod
    async def check_url(cls, session: ClientSession) -> None:
        "Async task to loop reading URL from the queue and check it is valid and reachable"
        while True:
            try:
                url = cls.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                async with session.get(url, timeout=cls.timeout) as response:
                    # Ignore forbidden links as browsers can sometimes still access them
                    if response.status == 403:
                        cls.urls_ignore[url] = 'Forbidden'
                    else:
                        response.raise_for_status()
            except ClientResponseError as e:
                # Ignore "too many requests" errors
                if e.status == 429:
                    cls.urls_ignore[url] = 'Too many requests'
                else:
                    cls.urls[url] = str(e)
            except Exception as e:
                cls.urls[url] = str(e)

            cls.queue.task_done()

    @classmethod
    async def check_all_urls(cls, args: Namespace) -> None:
        "Create a pool of async tasks to check URLs in parallel"
        async with ClientSession() as session:
            for url in cls.urls:
                cls.queue.put_nowait(url)

            n_pool_tasks = min(cls.queue.qsize(), args.parallel_url_checks)
            tasks = [
                asyncio.create_task(cls.check_url(session)) for _ in range(n_pool_tasks)
            ]
            await asyncio.gather(*tasks)

    @classmethod
    async def main(cls, args: Namespace) -> str | None:
        "Main async code"
        # Extract all links from all files
        files = {}
        for filestr in args.files or [DEFFILE]:
            # Only process each file once
            if (file := Path(filestr)) not in files:
                if not file.is_file():
                    return f'File "{file}" does not exist.'

                files[file] = cls(file)

        # Validate all URLs (using parallel pool of async tasks)
        if cls.urls and not args.no_urls:
            await cls.check_all_urls(args)

        # Now check and report all urls/links in all files
        bad = sum(not fp.check_ok(args) for fp in files.values())

        if bad > 0 and not args.no_fail:
            s = 's' if bad > 1 else ''
            return f'Errors found in {bad} file{s}.'

        return None


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
        help='max number of URL checks to perform in parallel (default=%(default)d)',
    )
    opt.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='print links found in file as they are checked',
    )
    opt.add_argument(
        '-f',
        '--no-fail',
        action='store_true',
        help='do not return final error code after failures',
    )
    opt.add_argument(
        '-w',
        '--no-warnings',
        action='store_true',
        help='do not print warnings for ignored URLs',
    )
    opt.add_argument(
        'files',
        nargs='*',
        help=f'one or more markdown files to check, default = "{DEFFILE}"',
    )

    return asyncio.run(File.main(opt.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
