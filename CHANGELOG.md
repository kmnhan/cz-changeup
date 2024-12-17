## v1.1.1 (2024-12-17)

### Fix

- add line breaks between changes for mdformat compatibility ([14ca08d](https://github.com/kmnhan/cz-changeup/commit/14ca08d61ca9bfc71262125d83e3e56601a20237))

## v1.1.0 (2024-12-10)

### Feat

- add support for linking external GitHub issues in changelog ([3daa390](https://github.com/kmnhan/cz-changeup/commit/3daa3906d675d19a7f0e1f269735a15157d2068c))

## v1.0.1 (2024-10-25)

### Fix

- properly handle breaking changes ([ef54285](https://github.com/kmnhan/cz-changeup/commit/ef5428575e24effa2c2fec8efccabef161274868))

## v1.0.0 (2024-10-25)

### BREAKING CHANGE

- Breaking changes will now be hidden from the commit body and will only appear in the breaking change section. The behavior can be controlled with the newly added option `changeup_hide_breaking`. ([ecda657](https://github.com/kmnhan/cz-changeup/commit/ecda657c5667a438fac0f2a2abd410415e50a48e))

  Adds option for hiding breaking changes from commit body in changelog.

### Feat

- add `changeup_hide_breaking` option ([ecda657](https://github.com/kmnhan/cz-changeup/commit/ecda657c5667a438fac0f2a2abd410415e50a48e))

  Adds option for hiding breaking changes from commit body in changelog.

## v0.3.0 (2024-10-08)

### Feat

- **link:** Improve issue linking in commit messages, closes [#3](https://github.com/kmnhan/cz-changeup/issues/3) ([9758f43](https://github.com/kmnhan/cz-changeup/commit/9758f43ca7e39c46eb77e5333223998f0deb3f9a))

  Now supports linking multiple issues by separating them with spaces. Each issue is now properly linked to its corresponding URL on the base URL provided.

## v0.2.0 (2024-10-04)

### Feat

- add automatic issue linking and more customization option ([9faf8be](https://github.com/kmnhan/cz-changeup/commit/9faf8be3db978a27036cfa499a09e62014b50846))

## v0.1.2 (2024-08-15)

### Fix

- **scope:** remove trailing whitespace in body ([e7383d9](https://github.com/kmnhan/cz-changeup/commit/e7383d924051cc4b0eb0f4d7a61da32941d200d9))

## v0.1.1 (2024-08-15)

### Fix

- change config ([3c6c7b9](https://github.com/kmnhan/cz-changeup/commit/3c6c7b9fa18c59cc813a0438a08ef9e6445b8f3f))

  Project configuration has been modified to include the link to the commit in the changelog. Also added all settings provided by this plugin to `pyproject.toml` for demonstration.

  This is the footer content added to demonstrate how the changelog is rendered.

### Refactor

- add license file ([518c296](https://github.com/kmnhan/cz-changeup/commit/518c29667f5b28440b447724b93b59a0976c1905))

## v0.1.0 (2024-08-15)

### Feat

- initial release ([8adf678](https://github.com/kmnhan/cz-changeup/commit/8adf678a19fa85e3dbf5015191c34e12bf4211ab))
