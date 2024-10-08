__all__ = ["ChangeupCz"]

import re

from commitizen import config, git
from commitizen.cz.conventional_commits import ConventionalCommitsCz
from jinja2 import PackageLoader

_issue_keywords = (
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
_issue_pattern = re.compile(
    r"(\b(?:" + "|".join(_issue_keywords) + r")\s+(#\d+(\s+#\d+)*)\b)", re.IGNORECASE
)


def linkify_issues(message: str, base_url: str) -> str:
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

    return _issue_pattern.sub(_replace_issue_with_link, message)


class ChangeupCz(ConventionalCommitsCz):
    conf = config.read_cfg()

    template = "CHANGELOG.md.j2"
    template_loader = PackageLoader("cz_changeup", "templates")

    repo_base_url: str = conf.settings.get("changeup_repo_base_url", "").strip(" /")
    show_hash: bool = conf.settings.get("changeup_show_hash", True)
    show_body: bool = conf.settings.get("changeup_show_body", True)
    body_indent: int = conf.settings.get("changeup_body_indent", 2)

    link_issues: bool = conf.settings.get("changeup_link_issues", True)

    scope_prefix: str = conf.settings.get("changeup_scope_prefix", "")
    scope_suffix: bool = conf.settings.get("changeup_scope_suffix", "")
    scope_separator: str = conf.settings.get("changeup_scope_separator", ": ")

    def changelog_message_builder_hook(
        self, parsed_message: dict, commit: git.GitCommit
    ) -> dict | list | None:
        msg = str(parsed_message["message"])
        scope = parsed_message.get("scope")

        if self.repo_base_url and self.show_hash:
            msg = (
                msg + f" ([{commit.rev[:7]}]({self.repo_base_url}/commit/{commit.rev}))"
            )

        if self.show_body and commit.body:
            msg += f"\n\n{' ' * self.body_indent}"
            body = ("\n\n" + (" " * self.body_indent)).join(
                [s.strip() for s in str(commit.body).split("\n") if s]
            )
            msg += f"{body}"

        if scope:
            scope = (
                f"{self.scope_prefix}{scope}{self.scope_suffix}{self.scope_separator}"
            )
            parsed_message["scope"] = scope

        if self.repo_base_url and self.link_issues:
            msg = linkify_issues(msg, self.repo_base_url)

        parsed_message["message"] = msg
        return parsed_message

    @property
    def template_extras(self) -> dict[str, str]:
        return {"repo_base_url": self.repo_base_url}
