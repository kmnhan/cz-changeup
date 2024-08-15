# cz-changeup

This plugin is a version of
[Commitizen](https://commitizen-tools.github.io/commitizen/)'s default conventional
style with a more informative changelog format.

## Installation

```bash
    pip install cz-changeup
```

## Configuration

Add to your `pyproject.toml`:

```toml
[tool.commitizen]
name = "cz_changeup"
```

The behavior of the plugin can be customized by providing the following options under `tool.commitizen`:

| Option                   | Description                                                                                           | Default | Example                        |
| ------------------------ | ----------------------------------------------------------------------------------------------------- | ------- | ------------------------------ |
| `changeup_repo_base_url` | The base URL for the repository. If given, adds a link to the commit for each entry in the changelog. | `""`    | `"https://github.com/my/repo"` |
| `changeup_show_body`     | Whether to include the commit body in the changelog.                                                  | `true`  |                                |
| `changeup_body_indent`   | The number of spaces to indent the commit body if `show_body` is set to `true`.                       | `2`     |                                |
