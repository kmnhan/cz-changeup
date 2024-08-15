__all__ = ["ChangeupCz"]

from commitizen import config, git
from commitizen.cz.conventional_commits import ConventionalCommitsCz


class ChangeupCz(ConventionalCommitsCz):
    conf = config.read_cfg()

    repo_base_url: str = conf.settings.get("changeup_repo_base_url", "").strip(" /")
    show_body: bool = conf.settings.get("changeup_show_body", True)
    body_indent: int = conf.settings.get("changeup_body_indent", 2)

    def changelog_message_builder_hook(
        self, parsed_message: dict, commit: git.GitCommit
    ) -> dict | list | None:
        msg = str(parsed_message["message"])

        if self.repo_base_url:
            msg = (
                msg + f" ([{commit.rev[:7]}]({self.repo_base_url}/commit/{commit.rev}))"
            )

        if self.show_body and commit.body:
            msg += f"\n\n{' ' * self.body_indent}"
            body = ("\n\n" + (" " * self.body_indent)).join(
                [s.strip() for s in str(commit.body).split("\n") if s]
            )
            msg += f"{body}"

        parsed_message["message"] = msg
        return parsed_message

    @property
    def template_extras(self) -> dict[str, str]:
        return {"repo_base_url": self.repo_base_url}
