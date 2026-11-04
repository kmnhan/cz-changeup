from __future__ import annotations

__all__ = ["ChangeupCz"]

import json
import os
import re
from functools import lru_cache
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from commitizen import config, git
from commitizen.cz.conventional_commits import ConventionalCommitsCz
from jinja2 import PackageLoader

_ISSUE_KEYWORDS = (
    "close",
    "closes",
    "closed",
    "fix",
    "fixes",
    "fixed",
    "resolve",
    "resolves",
    "resolved",
)
_ISSUE_PATTERN = re.compile(
    r"(\b(?:" + "|".join(_ISSUE_KEYWORDS) + r")\s+(#\d+(\s+#\d+)*)\b)", re.IGNORECASE
)
_ISSUE_PATTERN_EXTERNAL = re.compile(
    r"(?P<owner>[\w-]+)/(?P<repo>[\w-]+)/#(?P<issue_number>\d+)"
)
_COAUTHOR_TRAILER = re.compile(
    r"Co-authored-by:[ \t]+(?P<name>[^<>\r\n]+?)[ \t]*"
    r"<(?P<email>[^<>\r\n]+)>[ \t]*",
    re.IGNORECASE,
)
_COMMIT_TRAILER = re.compile(r"[A-Za-z][A-Za-z0-9-]*:[ \t]+\S.*")
_GITHUB_USERNAME = re.compile(r"(?!.*--)[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
_GITHUB_NOREPLY = re.compile(
    r"(?:\d+\+)?(?P<username>[A-Za-z0-9-]+)@users\.noreply\.github\.com",
    re.IGNORECASE,
)


def _github_username(email: str) -> str | None:
    if email.casefold().endswith("@users.noreply.github.com"):
        match = _GITHUB_NOREPLY.fullmatch(email)
        if match and _GITHUB_USERNAME.fullmatch(match["username"]):
            return match["username"]
        return None
    return _lookup_github_username(email.casefold())


@lru_cache(maxsize=256)
def _lookup_github_username(email: str) -> str | None:
    if not re.fullmatch(r'[^@\s<>"\\]+@[^@\s<>"\\]+', email):
        return None
    query = urlencode({"q": f"author-email:{email}", "per_page": 100})
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cz-changeup",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        request = Request(
            f"https://api.github.com/search/commits?{query}", headers=headers
        )
        with urlopen(request, timeout=2) as response:
            result = json.load(response)
    except (OSError, ValueError, HTTPException):
        return None
    if not isinstance(result, dict) or result.get("incomplete_results"):
        return None
    items = result.get("items")
    if not isinstance(items, list):
        return None
    usernames = {}
    for item in items:
        if not isinstance(item, dict):
            return None
        commit = item.get("commit")
        author = commit.get("author") if isinstance(commit, dict) else None
        if not isinstance(author, dict):
            return None
        author_email = author.get("email")
        if not isinstance(author_email, str) or author_email.casefold() != email:
            continue
        account = item.get("author")
        username = account.get("login") if isinstance(account, dict) else None
        if not isinstance(username, str) or not _GITHUB_USERNAME.fullmatch(username):
            return None
        usernames[username.casefold()] = username
    return next(iter(usernames.values())) if len(usernames) == 1 else None


def _split_coauthors(body: str, link_coauthors: bool = True) -> tuple[str, str]:
    lines = body.splitlines()
    end = len(lines)
    names = []
    remaining_lines = []
    while end:
        line = lines[end - 1]
        if not line.strip():
            remaining_lines.append(line)
            end -= 1
            continue
        trailer = _COAUTHOR_TRAILER.fullmatch(line)
        if trailer is None:
            if not _COMMIT_TRAILER.fullmatch(line):
                break
            remaining_lines.append(line)
        else:
            name = trailer["name"].strip()
            username = (
                _github_username(trailer["email"].strip()) if link_coauthors else None
            )
            if username:
                label = re.sub(r"([\\\[\]])", r"\\\1", name)
                name = f"[{label}](https://github.com/{username})"
            names.append(name)
        end -= 1

    if not names:
        return body, ""

    # GitHub separates its coauthor trailers from the description with a rule.
    if (
        end
        and re.fullmatch(r"-{3,}", lines[end - 1])
        and (end == 1 or not lines[end - 2].strip())
    ):
        end -= 1

    names.reverse()
    authors = (
        names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    )
    description = "\n".join(lines[:end]).rstrip("\n")
    if remaining_lines:
        description = "\n\n".join(
            part
            for part in (description, "\n".join(reversed(remaining_lines)).strip("\n"))
            if part
        )
    return description, f"Co-authored by {authors}."


def linkify_issues(message: str, base_url: str) -> str:
    """
    Converts issue references after keywords in a message to markdown links.

    Args:
        message (str): The message containing issue references.
        base_url (str): The base URL for the issue tracker.

    Returns:
        str: The message with issue references converted to markdown links.

    Example:
        >>> linkify_issues("This fixes #123.", "https://github.com/user/repo")
        'This fixes [#123](https://github.com/user/repo/issues/123).'
    """

    def _replace_issue_with_link(match):
        keyword = match.group(1)
        issue_numbers = match.group(2).split()
        issue_links = " ".join(
            [
                f"[{issue_number}]({base_url}/issues/{issue_number[1:]})"
                for issue_number in issue_numbers
            ]
        )
        return keyword.replace(match.group(2), issue_links)

    return _ISSUE_PATTERN.sub(_replace_issue_with_link, message)


def linkify_external_issues(text):
    """
    Detect and convert external GitHub issue references to markdown link addresses.

    Args:
        text (str): The input text containing GitHub issue references.

    Returns:
        str: The text with GitHub issue references converted to markdown links.

    Example:
        >>> linkify_external_issues("See user/repo/#123 for more info.")
        'See [user/repo/#123](https://github.com/user/repo/issues/123) for more info.'
    """

    def _replace_match(match):
        owner = match.group("owner")
        repo = match.group("repo")
        issue_number = match.group("issue_number")
        url = f"https://github.com/{owner}/{repo}/issues/{issue_number}"
        return f"[{match.group(0)}]({url})"

    return _ISSUE_PATTERN_EXTERNAL.sub(_replace_match, text)


class ChangeupCz(ConventionalCommitsCz):
    conf = config.read_cfg()

    template = "CHANGELOG.md.j2"
    template_loader = PackageLoader("cz_changeup", "templates")

    repo_base_url: str = conf.settings.get("changeup_repo_base_url", "").strip(" /")
    show_hash: bool = conf.settings.get("changeup_show_hash", True)
    show_body: bool = conf.settings.get("changeup_show_body", True)
    show_hash_breaking: bool = conf.settings.get("changeup_show_hash_breaking", True)
    hide_breaking: bool = conf.settings.get("changeup_hide_breaking", True)
    body_indent: int = conf.settings.get("changeup_body_indent", 2)

    link_issues: bool = conf.settings.get("changeup_link_issues", True)
    link_ext_issues: bool = conf.settings.get("changeup_link_external_issues", True)
    link_coauthors: bool = conf.settings.get("changeup_link_coauthors", True)

    scope_prefix: str = conf.settings.get("changeup_scope_prefix", "")
    scope_suffix: bool = conf.settings.get("changeup_scope_suffix", "")
    scope_separator: str = conf.settings.get("changeup_scope_separator", ": ")

    def changelog_message_builder_hook(
        self, parsed_message: dict, commit: git.GitCommit
    ) -> dict | list | None:
        msg = str(parsed_message["message"])
        scope = parsed_message.get("scope")

        in_breaking_section = (
            parsed_message.get("change_type", None) == "BREAKING CHANGE"
        )

        add_hash: bool = (self.repo_base_url != "") and self.show_hash

        if in_breaking_section:
            description, credit = _split_coauthors(msg, self.link_coauthors)
            msg = self.parse_body_indent(
                "\n\n".join(part for part in (description, credit) if part)
            )

            if not self.show_hash_breaking:
                add_hash = False

        if add_hash:
            msg = (
                msg + f" ([{commit.rev[:7]}]({self.repo_base_url}/commit/{commit.rev}))"
            )

        if self.show_body and commit.body and not in_breaking_section:
            body, credit = _split_coauthors(str(commit.body), self.link_coauthors)
            if self.hide_breaking and "BREAKING CHANGE:" in body:
                body = body.split("BREAKING CHANGE:")[0].strip()
            body = "\n\n".join(part for part in (body, credit) if part)

            if body:
                msg += f"\n\n{' ' * self.body_indent}{self.parse_body_indent(body)}"

        if scope:
            scope = (
                f"{self.scope_prefix}{scope}{self.scope_suffix}{self.scope_separator}"
            )
            parsed_message["scope"] = scope

        if self.repo_base_url and self.link_issues:
            msg = linkify_issues(msg, self.repo_base_url)

        if self.link_ext_issues:
            msg = linkify_external_issues(msg)

        parsed_message["message"] = msg
        return parsed_message

    def parse_body_indent(self, body: str):
        lines = body.strip("\r\n").splitlines()
        return "\n".join(
            (" " * self.body_indent if index and line else "") + line
            for index, line in enumerate(lines)
        )

    @property
    def template_extras(self) -> dict[str, str]:
        return {"repo_base_url": self.repo_base_url}
