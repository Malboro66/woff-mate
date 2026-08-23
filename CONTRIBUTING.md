# Contributing to WoFF Mate

Thank you for your interest in improving WoFF Mate.

## Before You Start

For non-trivial changes, check the existing [issues](https://github.com/Malboro66/woff-mate/issues) and the [WoFF Mate Development Project](https://github.com/users/Malboro66/projects/1) first. This helps avoid duplicate work and keeps implementation aligned with the project's dependency and quality-gate model.

## Development Setup

Requirements:

- Windows 10/11 for full platform validation
- Python 3.10 through 3.14
- Git

Create an environment and install the project with development dependencies:

```powershell
git clone https://github.com/Malboro66/woff-mate.git
cd woff-mate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Making Changes

- Keep changes focused on one issue or clearly defined concern.
- Preserve Python 3.10 compatibility unless the supported range is intentionally changed.
- Avoid unrelated refactors in bug-fix or narrowly scoped feature work.
- Treat WOFF campaign files as read-only inputs.
- Do not commit personal `config.json` files, real player data, databases, logs, build outputs, or other local artifacts.
- Use sanitized samples when regression fixtures are required.
- Update tests and documentation when behavior or public contracts change.

## Validation

Run the core checks before opening a pull request:

```powershell
python scripts/validate_project_graph.py
python -m pytest -q
pyright
```

The CI workflow additionally validates packaging, installed entry points, module imports, and a Windows PyInstaller smoke build.

## Pull Requests

A good pull request should:

1. Explain the problem being solved.
2. Keep the implementation scoped and reviewable.
3. Reference the relevant issue when one exists.
4. Include or update tests for behavior changes.
5. Keep CI and Pyright green.
6. Update documentation and engineering contracts when required.

Use `Closes #<issue>` in the pull request description when the change fully resolves an issue.

## Bug Reports

When reporting a bug, include:

- WoFF Mate version or commit
- Python version
- Windows version
- Reproduction steps
- Expected and observed behavior
- Relevant sanitized logs or samples

Never publish personal campaign data, user-specific paths, or other sensitive information in an issue.

## Security Reports

Do not use public issues for vulnerabilities or other security-sensitive reports. Follow [SECURITY.md](SECURITY.md).

## License

By contributing to this repository, you agree that your contribution will be licensed under the project's [MIT License](LICENSE).
