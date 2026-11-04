import json
from http.client import IncompleteRead
from io import BytesIO, StringIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from commitizen import changelog, config, git
from docutils import nodes
from docutils.core import publish_doctree
from jinja2 import Environment
from myst_parser.parsers.docutils_ import Parser

import cz_changeup.cz_changeup as changeup_module
from cz_changeup.cz_changeup import ChangeupCz


@pytest.fixture(autouse=True)
def _reset_github_lookup(monkeypatch):
    changeup_module._lookup_github_username.cache_clear()
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        changeup_module,
        "urlopen",
        Mock(side_effect=AssertionError("Tests must not make live GitHub requests")),
    )
    yield
    changeup_module._lookup_github_username.cache_clear()


@pytest.fixture
def plugin():
    plugin = ChangeupCz(config.BaseConfig())
    plugin.repo_base_url = "https://github.com/example/project"
    plugin.show_hash = False
    plugin.show_hash_breaking = False
    plugin.show_body = True
    plugin.hide_breaking = True
    plugin.body_indent = 2
    plugin.link_issues = True
    plugin.link_ext_issues = True
    plugin.link_coauthors = False
    plugin.scope_prefix = "**"
    plugin.scope_suffix = ""
    plugin.scope_separator = ":** "
    return plugin


def build_message(plugin, body, message="preserve changelog formatting", **parsed):
    commit = git.GitCommit("123456789abcdef", "fix: " + message, body)
    return plugin.changelog_message_builder_hook(
        {"message": message, "change_type": "fix", **parsed}, commit
    )


def render_document(plugin, changes):
    rendered = (
        Environment(loader=plugin.template_loader, trim_blocks=True)
        .get_template(plugin.template)
        .render(tree=[{"version": "v1.2.3", "date": "2026-11-04", "changes": changes}])
    )
    warnings = StringIO()
    document = publish_doctree(
        "# Changelog\n" + rendered,
        parser=Parser(),
        settings_overrides={"warning_stream": warnings, "halt_level": 2},
    )
    assert warnings.getvalue() == ""
    return document


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", ""),
        ("\n\nFirst paragraph.\n\n", "First paragraph."),
        ("A wrapped\nparagraph.", "A wrapped\n  paragraph."),
        (
            "First paragraph.\n\nSecond paragraph.",
            "First paragraph.\n\n  Second paragraph.",
        ),
        (
            "- First item.\n  - Nested item.\n- Second item.",
            "- First item.\n    - Nested item.\n  - Second item.",
        ),
        (
            "```python\nif ready:\n    run()\n```",
            "```python\n  if ready:\n      run()\n  ```",
        ),
        (
            "Example:\n\n    if ready:\n        run()",
            "Example:\n\n      if ready:\n          run()",
        ),
    ],
)
def test_body_preserves_markdown_structure(plugin, body, expected):
    assert plugin.parse_body_indent(body) == expected


def test_body_uses_configured_indent(plugin):
    plugin.body_indent = 4

    assert plugin.parse_body_indent("First line.\nSecond line.") == (
        "First line.\n    Second line."
    )
    assert build_message(plugin, "First line.\nSecond line.")["message"] == (
        "preserve changelog formatting\n\n    First line.\n    Second line."
    )


def test_body_can_be_hidden(plugin):
    plugin.show_body = False

    assert build_message(plugin, "A body that must be hidden.")["message"] == (
        "preserve changelog formatting"
    )


@pytest.mark.parametrize("hide_breaking", [True, False])
def test_body_breaking_change_visibility(plugin, hide_breaking):
    plugin.hide_breaking = hide_breaking
    body = "Describes the change.\n\nBREAKING CHANGE: Use the new API."

    expected = "preserve changelog formatting\n\n  Describes the change."
    if not hide_breaking:
        expected += "\n\n  BREAKING CHANGE: Use the new API."

    assert build_message(plugin, body)["message"] == expected


def test_breaking_section_does_not_repeat_commit_body(plugin):
    message = "Use the new API.\n\n- Rename the argument.\n- Update callers."

    parsed = build_message(
        plugin,
        "This body must not be repeated.",
        message=message,
        change_type="BREAKING CHANGE",
    )

    assert parsed["message"] == (
        "Use the new API.\n\n  - Rename the argument.\n  - Update callers."
    )


def test_scope_hash_and_issue_links_are_preserved(plugin):
    plugin.show_hash = True
    parsed = build_message(plugin, "Fixes #42.", scope="parser")

    assert parsed["scope"] == "**parser:** "
    assert parsed["message"] == (
        "preserve changelog formatting "
        "([1234567](https://github.com/example/project/commit/123456789abcdef))"
        "\n\n  Fixes [#42](https://github.com/example/project/issues/42)."
    )


def test_generated_changelog_renders_lists_and_code(plugin):
    body = (
        "A wrapped\nparagraph.\n\n"
        "- First item.\n  - Nested item.\n- Second item.\n\n"
        "```python\nif ready:\n    run()\n```\n\n"
        "Another paragraph."
    )
    parsed = build_message(plugin, body)
    document = render_document(plugin, {"Fix": [parsed]})

    lists = list(document.findall(nodes.bullet_list))
    assert len(lists) == 3
    assert len(lists[0].children) == 1
    assert len(lists[1].children) == 2
    assert len(lists[2].children) == 1
    assert next(iter(document.findall(nodes.literal_block))).astext() == (
        "if ready:\n    run()"
    )
    paragraphs = [node.astext() for node in document.findall(nodes.paragraph)]
    assert "A wrapped\nparagraph." in paragraphs
    assert "Another paragraph." in paragraphs


@pytest.mark.parametrize("separator", ["", "---------\n\n"])
def test_coauthor_trailers_become_a_short_credit(plugin, separator):
    body = (
        "Describes the change.\n\n"
        + separator
        + "Co-authored-by: Alice Example <alice@example.com>\n"
        "co-AUTHORED-by: Bob Example <bob@example.com>\n\n"
    )

    assert build_message(plugin, body)["message"] == (
        "preserve changelog formatting\n\n  Describes the change."
        "\n\n  Co-authored by Alice Example and Bob Example."
    )


def test_coauthor_only_body_becomes_a_short_credit(plugin):
    parsed = build_message(plugin, "Co-authored-by: Alice Example <alice@example.com>")

    assert parsed["message"] == (
        "preserve changelog formatting\n\n  Co-authored by Alice Example."
    )


def test_github_coauthor_separator_does_not_create_a_transition(plugin):
    description = (
        "Adds ML-based denoising. The function can be accessed with "
        "`erlab.analysis.image.ml.denoise`, and can also be performed interactively "
        "with the new `dntool` available in ImageTool Manager."
    )
    parsed = build_message(
        plugin,
        description + "\n\n---------\n\n"
        "Co-authored-by: Younsik Kim "
        "<82874859+Younsik-phys@users.noreply.github.com>",
    )

    assert parsed["message"] == (
        "preserve changelog formatting\n\n  "
        + description
        + "\n\n  Co-authored by Younsik Kim."
    )
    document = render_document(plugin, {"Fix": [parsed]})
    assert not list(document.findall(nodes.transition))
    assert "Co-authored by Younsik Kim." in document.astext()
    assert "users.noreply.github.com" not in document.astext()


def test_coauthor_credit_preserves_other_horizontal_rules(plugin):
    body = (
        "First paragraph.\n\n---------\n\nSecond paragraph.\n\n"
        "---------\n\nCo-authored-by: Alice Example <alice@example.com>"
    )

    assert build_message(plugin, body)["message"] == (
        "preserve changelog formatting\n\n  First paragraph.\n\n  ---------"
        "\n\n  Second paragraph.\n\n  Co-authored by Alice Example."
    )


@pytest.mark.parametrize(
    "trailers",
    [
        (
            "Co-authored-by: Alice Example <alice@example.com>\n"
            "Signed-off-by: Reviewer <reviewer@example.com>"
        ),
        (
            "Signed-off-by: Reviewer <reviewer@example.com>\n"
            "Co-authored-by: Alice Example <alice@example.com>"
        ),
    ],
)
def test_coauthor_credit_preserves_other_git_trailers(plugin, trailers):
    parsed = build_message(plugin, "Description.\n\n---------\n\n" + trailers)

    assert "Signed-off-by: Reviewer <reviewer@example.com>" in parsed["message"]
    assert parsed["message"].count("Co-authored by Alice Example.") == 1
    assert "alice@example.com" not in parsed["message"]
    assert "---------" not in parsed["message"]
    document = render_document(plugin, {"Fix": [parsed]})
    assert not list(document.findall(nodes.transition))


def test_coauthor_credit_preserves_separate_colon_paragraphs(plugin):
    parsed = build_message(
        plugin,
        "Description.\n\nNote: First paragraph.\n\nCaution: Separate paragraph.\n\n"
        "Co-authored-by: Alice Example <alice@example.com>",
    )

    assert parsed["message"] == (
        "preserve changelog formatting\n\n  Description.\n\n  Note: First paragraph."
        "\n\n  Caution: Separate paragraph.\n\n  Co-authored by Alice Example."
    )
    document = render_document(plugin, {"Fix": [parsed]})
    paragraphs = [node.astext() for node in document.findall(nodes.paragraph)]
    assert "Note: First paragraph." in paragraphs
    assert "Caution: Separate paragraph." in paragraphs


@pytest.mark.parametrize(
    "body",
    [
        "Example:\n\n```text\nCo-authored-by: Alice Example <alice@example.com>\n```",
        "Example:\n\n    Co-authored-by: Alice Example <alice@example.com>",
    ],
)
def test_coauthor_examples_remain_code(plugin, body):
    parsed = build_message(plugin, body)

    assert "Co-authored by" not in parsed["message"]
    document = render_document(plugin, {"Fix": [parsed]})
    assert next(iter(document.findall(nodes.literal_block))).astext().rstrip("\n") == (
        "Co-authored-by: Alice Example <alice@example.com>"
    )


def test_coauthor_credit_is_hidden_with_commit_body(plugin):
    plugin.show_body = False

    parsed = build_message(
        plugin,
        "Describes the change.\n\n---------\n\n"
        "Co-authored-by: Alice Example <alice@example.com>",
    )

    assert parsed["message"] == "preserve changelog formatting"


def test_breaking_section_formats_coauthor_credit(plugin):
    parsed = build_message(
        plugin,
        "This body must not be repeated.",
        message=(
            "Use the new API.\n\n---------\n\n"
            "Co-authored-by: Alice Example <alice@example.com>"
        ),
        change_type="BREAKING CHANGE",
    )

    assert parsed["message"] == ("Use the new API.\n\n  Co-authored by Alice Example.")


@pytest.mark.parametrize("breaking", ["", "BREAKING CHANGE: Use the new API.\n\n"])
def test_commitizen_pipeline_renders_coauthor_credit(plugin, breaking):
    commit = git.GitCommit(
        "123456789abcdef",
        "fix(parser): preserve changelog formatting",
        "Describes the change.\n\n"
        + breaking
        + "---------\n\nCo-authored-by: Alice Example <alice@example.com>",
    )
    tree = list(
        changelog.generate_tree_from_commits(
            [commit],
            [],
            commit_parser=plugin.commit_parser,
            changelog_pattern=plugin.changelog_pattern,
            changelog_message_builder_hook=plugin.changelog_message_builder_hook,
        )
    )
    document = render_document(plugin, tree[0]["changes"])

    assert document.astext().count("Co-authored by Alice Example.") == 1
    assert "alice@example.com" not in document.astext()
    assert not list(document.findall(nodes.transition))
    if breaking:
        assert "Use the new API." in document.astext()


@pytest.mark.parametrize(
    ("email", "username"),
    [
        ("82874859+Younsik-phys@users.noreply.github.com", "Younsik-phys"),
        ("Alice-Example@users.noreply.github.com", "Alice-Example"),
        ("42+Alice@USERS.NOREPLY.GITHUB.COM", "Alice"),
    ],
)
def test_coauthor_noreply_address_links_offline(plugin, email, username):
    plugin.link_coauthors = True
    parsed = build_message(plugin, f"Co-authored-by: Alice Example <{email}>")

    assert parsed["message"] == (
        "preserve changelog formatting\n\n  Co-authored by "
        f"[Alice Example](https://github.com/{username})."
    )
    changeup_module.urlopen.assert_not_called()


@pytest.mark.parametrize(
    "username",
    ["-alice", "alice-", "alice--example", "alice/other", "alice_name", "a" * 40],
)
def test_invalid_noreply_username_keeps_plain_credit(plugin, username):
    plugin.link_coauthors = True
    parsed = build_message(
        plugin,
        f"Co-authored-by: Alice Example <42+{username}@users.noreply.github.com>",
    )

    assert parsed["message"].endswith("Co-authored by Alice Example.")
    changeup_module.urlopen.assert_not_called()


def test_coauthor_link_escapes_markdown_name(plugin):
    plugin.link_coauthors = True
    name = r"Alice [Lab]\Team"
    parsed = build_message(
        plugin, f"Co-authored-by: {name} <42+alice@users.noreply.github.com>"
    )
    document = render_document(plugin, {"Fix": [parsed]})
    reference = next(iter(document.findall(nodes.reference)))

    assert reference["refuri"] == "https://github.com/alice"
    assert reference.astext() == name
    assert "users.noreply.github.com" not in document.astext()


def test_coauthor_links_can_be_disabled(plugin, monkeypatch):
    resolver = Mock(
        side_effect=AssertionError("Disabled links must not resolve accounts")
    )
    monkeypatch.setattr(changeup_module, "_github_username", resolver)
    parsed = build_message(
        plugin,
        "Co-authored-by: Alice Example <42+alice@users.noreply.github.com>\n"
        "Co-authored-by: Bob Example <bob@example.com>",
    )

    assert parsed["message"].endswith("Co-authored by Alice Example and Bob Example.")
    resolver.assert_not_called()


def search_result(email="alice@example.com", username="Alice-Example"):
    return {
        "commit": {"author": {"email": email}},
        "author": {"login": username},
    }


def mock_search(monkeypatch, result):
    opener = Mock(return_value=BytesIO(json.dumps(result).encode()))
    monkeypatch.setattr(changeup_module, "urlopen", opener)
    return opener


def test_coauthor_email_lookup_verifies_email_and_caches_result(plugin, monkeypatch):
    plugin.link_coauthors = True
    opener = mock_search(
        monkeypatch,
        {
            "items": [
                search_result("other@example.com", "other"),
                search_result("ALICE@example.com", "Alice-Example"),
            ]
        },
    )
    for email in ["Alice@example.com", "alice@EXAMPLE.com"]:
        parsed = build_message(plugin, f"Co-authored-by: Alice Example <{email}>")
        assert parsed["message"].endswith(
            "Co-authored by [Alice Example](https://github.com/Alice-Example)."
        )
    opener.assert_called_once()
    request = opener.call_args.args[0]
    assert request.full_url.startswith("https://api.github.com/search/commits?")
    assert parse_qs(urlsplit(request.full_url).query) == {
        "q": ["author-email:alice@example.com"],
        "per_page": ["100"],
    }
    assert opener.call_args.kwargs == {"timeout": 2}
    assert request.get_header("Authorization") is None


@pytest.mark.parametrize("token_name", ["GH_TOKEN", "GITHUB_TOKEN"])
def test_coauthor_lookup_uses_optional_token(monkeypatch, token_name):
    monkeypatch.setenv(token_name, "test-token")
    opener = mock_search(monkeypatch, {"items": [search_result()]})

    assert changeup_module._github_username("alice@example.com") == "Alice-Example"
    assert opener.call_args.args[0].get_header("Authorization") == "Bearer test-token"


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {},
        {"items": None},
        {"items": []},
        {"items": [None]},
        {"items": [{"commit": None, "author": {"login": "alice"}}]},
        {"items": [{"commit": {"author": None}, "author": {"login": "alice"}}]},
        {
            "items": [
                {"commit": {"author": {"email": "alice@example.com"}}, "author": None}
            ]
        },
        {"items": [search_result("other@example.com")]},
        {"items": [search_result(username="alice/other")]},
        {"items": [search_result(), search_result(username="another-account")]},
        {"items": [search_result()], "incomplete_results": True},
    ],
)
def test_unresolved_coauthor_lookup_keeps_plain_credit(plugin, monkeypatch, result):
    plugin.link_coauthors = True
    mock_search(monkeypatch, result)
    parsed = build_message(plugin, "Co-authored-by: Alice Example <alice@example.com>")

    assert parsed["message"].endswith("Co-authored by Alice Example.")
    assert "alice@example.com" not in parsed["message"]


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout"),
        URLError("offline"),
        IncompleteRead(b"partial"),
        HTTPError(
            "https://api.github.com/search/commits", 403, "rate limited", {}, BytesIO()
        ),
    ],
    ids=["timeout", "offline", "incomplete-response", "rate-limit"],
)
def test_failed_coauthor_lookup_is_silent_and_cached(
    plugin, monkeypatch, error, capsys
):
    plugin.link_coauthors = True
    opener = Mock(side_effect=error)
    monkeypatch.setattr(changeup_module, "urlopen", opener)

    for _ in range(2):
        parsed = build_message(
            plugin, "Co-authored-by: Alice Example <alice@example.com>"
        )
        assert parsed["message"].endswith("Co-authored by Alice Example.")

    opener.assert_called_once()
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_malformed_coauthor_lookup_json_keeps_plain_credit(plugin, monkeypatch):
    plugin.link_coauthors = True
    monkeypatch.setattr(
        changeup_module, "urlopen", Mock(return_value=BytesIO(b"not JSON"))
    )
    parsed = build_message(plugin, "Co-authored-by: Alice Example <alice@example.com>")

    assert parsed["message"].endswith("Co-authored by Alice Example.")


def test_invalid_email_cannot_add_search_qualifiers(plugin):
    plugin.link_coauthors = True
    parsed = build_message(
        plugin, "Co-authored-by: Alice Example <alice@example.com author:other>"
    )

    assert parsed["message"].endswith("Co-authored by Alice Example.")
    changeup_module.urlopen.assert_not_called()


@pytest.mark.parametrize("breaking", [False, True])
def test_coauthor_profile_link_renders_without_email(plugin, breaking):
    plugin.link_coauthors = True
    body = (
        "Use the new API.\n\n---------\n\n"
        "Co-authored-by: Younsik Kim <82874859+Younsik-phys@users.noreply.github.com>"
    )
    parsed = (
        build_message(plugin, "", message=body, change_type="BREAKING CHANGE")
        if breaking
        else build_message(plugin, body)
    )
    document = render_document(plugin, {"Fix": [parsed]})
    references = list(document.findall(nodes.reference))

    assert len(references) == 1
    assert references[0].astext() == "Younsik Kim"
    assert references[0]["refuri"] == "https://github.com/Younsik-phys"
    assert "@" not in document.astext()
    assert not list(document.findall(nodes.transition))
