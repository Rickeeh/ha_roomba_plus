#!/usr/bin/env python3
"""Reject private data in newly added lines.

WHY THIS EXISTS. Test fixtures here come from testers' diagnostics and
logs, and those carry home addresses, robot ids and passwords. A value
copied from a log into a test is easy to miss in review: a reviewer
reads for logic; this reads for what must never be published.

WHAT IT LOOKS AT. Only lines a change adds, so data already in the
history does not fail every run, and a new leak cannot hide behind it:

  - private IPv4 addresses (10/8, 172.16/12, 192.168/16) -- tests use
    the documentation ranges 192.0.2.0/24, 198.51.100.0/24 and
    203.0.113.0/24 instead (RFC 5737)
  - MAC addresses, except obvious placeholders
  - robot ids (BLIDs: 16 upper-case hex digits) and local robot
    passwords (`:1:<10 digits>:<16 characters>`)
  - e-mail addresses outside example domains and noreply addresses
  - AWS access keys (iRobot's cloud signs with them), GitHub tokens,
    JWTs and bearer tokens

WHICH LINES. `--base REV` compares against REV (CI passes the pushed
range or the pull request's base); `--staged` checks what is about to
be committed; `--all` checks every tracked file, for an audit. With no
option it compares against `origin/main`, which is what a release
package will add on GitHub.

A line that must keep such a value -- a third-party licence, say -- is
let through by a path in ALLOWED_PATHS, not by a marker in the line:
a marker is one copy-paste away from a real leak.

Exit 0: nothing found. Exit 1: findings, printed as path:line and the
category -- never the value itself, so the CI log does not republish it.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

#: Files whose added lines are not checked: third-party text that names
#: its authors, and nothing else.
ALLOWED_PATHS: tuple[str, ...] = (
    "custom_components/roomba_plus/fonts/",
)

#: Binary files are skipped; git reports them without lines anyway.
_BINARY_SUFFIXES = (".png", ".jpg", ".gif", ".ico", ".ttf", ".zip", ".woff", ".woff2")

_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
#: Written in pieces so this file does not fail its own check.
_PRIVATE_NETS = tuple(
    ipaddress.ip_network(".".join(parts))
    for parts in (("10", "0", "0", "0/8"), ("172", "16", "0", "0/12"), ("192", "168", "0", "0/16"))
)
_MAC = re.compile(r"(?i)(?<![0-9a-f:])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f:-])")
_PLACEHOLDER_MACS = (
    re.compile(r"(?i)^00([:-]00){5}$"),
    re.compile(r"(?i)^ff([:-]ff){5}$"),
    re.compile(r"(?i)^aa[:-]bb[:-]cc[:-]dd[:-]ee[:-](ff|0[0-9])$"),
    re.compile(r"(?i)^00[:-]11[:-]22[:-]33[:-]44[:-][0-9a-f]{2}$"),
    re.compile(r"(?i)^02([:-]00){4}[:-][0-9a-f]{2}$"),
    re.compile(r"(?i)^11[:-]22[:-]33[:-]44[:-]55[:-]66$"),
)
#: A BLID has letters and digits; a run of digits alone is a number.
_BLID = re.compile(r"(?<![0-9A-Za-z])(?=[0-9A-F]*[A-F])(?=[0-9A-F]*[0-9])[0-9A-F]{16}(?![0-9A-Za-z])")
_PLACEHOLDER_BLIDS = frozenset({
    "0123456789ABCDEF", "FEDCBA9876543210", "1234567890ABCDEF",
    "ABCDEF1234567890", "DEADBEEFDEADBEEF",
})
_ROBOT_PASSWORD = re.compile(r":1:(\d{10}):[A-Za-z0-9]{16}")
_PLACEHOLDER_PASSWORD_TIME = "1234567890"
_EMAIL = re.compile(
    r"(?<![\w.+-])[\w.+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![\w.-])"
)
#: `icon@2x.png` and `git@v0.1.11a6` are file names and pins, not mail.
_FILE_SUFFIXES = frozenset({"png", "jpg", "gif", "svg", "json", "py", "md", "yaml", "yml", "txt", "zip"})
_EXAMPLE_DOMAINS = re.compile(
    r"(?i)(^|\.)(example\.(com|org|net)|invalid|test|localhost|"
    r"users\.noreply\.github\.com|anthropic\.com)$"
)
_SECRETS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{24,}")),
)


@dataclass(frozen=True)
class Finding:
    """One category at one place; deliberately without the value."""

    path: str
    line: int
    category: str


def categories(text: str) -> list[str]:
    """The kinds of private data in one line, in a stable order."""
    found: list[str] = []
    for raw in _IPV4.findall(text):
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if any(address in net for net in _PRIVATE_NETS):
            found.append("private IPv4 address")
            break
    for mac in _MAC.finditer(text):
        if not any(p.match(mac.group(0)) for p in _PLACEHOLDER_MACS):
            found.append("MAC address")
            break
    if any(b not in _PLACEHOLDER_BLIDS for b in _BLID.findall(text)):
        found.append("robot id (BLID)")
    if any(t != _PLACEHOLDER_PASSWORD_TIME for t in _ROBOT_PASSWORD.findall(text)):
        found.append("robot password")
    if any(
        not _EXAMPLE_DOMAINS.search(d) and d.rsplit(".", 1)[-1].lower() not in _FILE_SUFFIXES
        for d in _EMAIL.findall(text)
    ):
        found.append("e-mail address")
    found.extend(name for name, pattern in _SECRETS if pattern.search(text))
    return found


def added_lines(diff: str) -> Iterator[tuple[str, int, str]]:
    """(path, line number, text) for every line a unified diff adds."""
    path: str | None = None
    line = 0
    for row in diff.splitlines():
        if row.startswith("+++ "):
            target = row[4:]
            path = target[2:] if target.startswith("b/") else None
        elif row.startswith("@@"):
            match = re.search(r"\+(\d+)", row)
            line = int(match.group(1)) if match else 0
        elif path is None:
            continue
        elif row.startswith("+"):
            yield path, line, row[1:]
            line += 1
        elif not row.startswith("-"):
            line += 1


def find(lines: Iterable[tuple[str, int, str]]) -> list[Finding]:
    """Findings in the given lines, allowed paths and binaries left out."""
    findings: list[Finding] = []
    for path, number, text in lines:
        if path.startswith(ALLOWED_PATHS) or path.endswith(_BINARY_SUFFIXES):
            continue
        findings.extend(Finding(path, number, c) for c in categories(text))
    return findings


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _all_lines() -> Iterator[tuple[str, int, str]]:
    for path in _git("ls-files").splitlines():
        if path.startswith(ALLOWED_PATHS) or path.endswith(_BINARY_SUFFIXES):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                for number, text in enumerate(handle, start=1):
                    yield path, number, text
        except (OSError, UnicodeDecodeError):
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reject private data in newly added lines.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--base", help="compare against this revision")
    mode.add_argument("--staged", action="store_true", help="check the staged changes")
    mode.add_argument("--all", action="store_true", help="check every tracked file")
    args = parser.parse_args(argv)

    if args.all:
        lines: Iterable[tuple[str, int, str]] = _all_lines()
        what = "every tracked file"
    elif args.staged:
        lines = added_lines(_git("diff", "--cached", "--unified=0", "--no-color"))
        what = "the staged changes"
    else:
        base = args.base or "origin/main"
        try:
            diff = _git("diff", "--unified=0", "--no-color", f"{base}...HEAD")
        except subprocess.CalledProcessError:
            print(f"::warning::{base} is not available; nothing was checked")
            return 0
        lines = added_lines(diff)
        what = f"lines added since {base}"

    findings = find(lines)
    if not findings:
        print(f"OK: no private data in {what}")
        return 0
    print(f"{len(findings)} finding(s) in {what}:\n")
    for f in findings:
        print(f"::error file={f.path},line={f.line}::{f.category}")
    print(
        "\n  Use placeholders: 192.0.2.x for addresses, aa:bb:cc:dd:ee:ff for\n"
        "  MACs, 0123456789ABCDEF for robot ids, user@example.com for\n"
        "  accounts. A third-party file that names its authors goes in\n"
        "  ALLOWED_PATHS."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
