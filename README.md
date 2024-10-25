# cz-changeup

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cz-changeup)](https://pypi.org/project/cz-changeup)
[![PyPI - Version](https://img.shields.io/pypi/v/cz-changeup)](https://pypi.org/project/cz-changeup)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/cz-changeup)](https://anaconda.org/conda-forge/cz-changeup)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

This plugin is a version of
[Commitizen](https://commitizen-tools.github.io/commitizen/)'s default conventional
style that provides more flexibility in the changelog format.

## Installation

With pip:

```bash
pip install cz-changeup
```

With conda:

```bash
conda install -c conda-forge cz-changeup
```

## Configuration

Add to your `pyproject.toml`:

```toml
[tool.commitizen]
name = "cz_changeup"
```

The behavior of the plugin can be customized by providing the following options under `tool.commitizen`:

| Option                     | Description                                                                                                                                      | Default |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------- |
| `changeup_repo_base_url`   | The base URL for the repository, for instance `"https://github.com/my/repo"`.                                                                    | `""`    |
| `changeup_show_hash`       | Whether to add a link to the commit for each entry in the changelog. If `changeup_repo_base_url` is provided, the hash are linked to the commit. | `true`  |
| `changeup_show_body`       | Whether to include the commit body in the changelog.                                                                                             | `true`  |
| `changeup_hide_breaking`   | Whether to include the breaking changes section also in the the commit body if `changeup_show_body` is true. This prevents duplicate entries.    | `true`  |
| `changeup_body_indent`     | The number of spaces to indent the commit body if `changeup_show_body` is set to `true`.                                                         | `2`     |
| `changeup_link_issues`     | If `true`, tries to convert issue numbers in phrases like `closes #21` to links. Only works if `changeup_repo_base_url` is provided.             | `true`  |
| `changeup_scope_prefix`    | Prefix for the scope of the change.                                                                                                              | `"**"`  |
| `changeup_scope_suffix`    | Suffix for the scope of the change.                                                                                                              | `"**"`  |
| `changeup_scope_separator` | Separator between the scope and the message.                                                                                                     | `": "`  |
