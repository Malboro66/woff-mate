# ✈️ WoFF Mate

> An open-source companion application for *Wings Over Flanders Fields: Between Heaven & Hell II*.

[![CI](https://img.shields.io/github/actions/workflow/status/Malboro66/woff-mate/ci.yml?branch=main&label=CI&logo=github)](https://github.com/Malboro66/woff-mate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10--3.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white)](https://github.com/Malboro66/woff-mate)
[![License: MIT](https://img.shields.io/github/license/Malboro66/woff-mate)](LICENSE)
[![Pyright](https://img.shields.io/badge/type%20checked-Pyright-blue)](pyrightconfig.json)
[![pytest](https://img.shields.io/badge/tested%20with-pytest-0A9EDC?logo=pytest&logoColor=white)](https://github.com/Malboro66/woff-mate/actions)
![Read Only](https://img.shields.io/badge/game%20integration-read--only-success)
![Status](https://img.shields.io/badge/status-active%20development-orange)

[![Last Commit](https://img.shields.io/github/last-commit/Malboro66/woff-mate)](https://github.com/Malboro66/woff-mate/commits/main)
[![Issues](https://img.shields.io/github/issues/Malboro66/woff-mate)](https://github.com/Malboro66/woff-mate/issues)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen)](CONTRIBUTING.md)

WoFF Mate monitors WOFF campaign data in real time, extracts and normalizes pilot and mission information, and stores it in a local SQLite database. On top of that data it provides RPG-style pilot state, squadron context, and narrative mission diary foundations for a richer campaign companion experience.

> **Read-only integration:** WoFF Mate observes and processes game-generated files. It does not intentionally modify WOFF campaign files.

## Features

- 🛩️ **Real-time campaign monitoring** — reacts to game-generated file changes while keeping ingestion bounded and deterministic.
- 👨‍✈️ **Pilot tracking** — builds a persistent record from WOFF pilot and dossier data.
- 🎯 **Mission ingestion** — parses mission logs and stores structured mission information.
- 🎖️ **Victories and awards** — tracks combat victories, medals, and related campaign data.
- 👥 **Wingmen and squadron context** — maintains AI pilot and squadron information.
- 🧠 **RPG layer** — tracks fatigue, morale, and stress from campaign history.
- 📖 **Dynamic diary** — generates narrative mission records from stored campaign events.
- 💾 **SQLite persistence** — uses transactional local storage for campaign state.
- 🔒 **Read-only game integration** — keeps the game installation and campaign files outside the application's write path.

## Quick Start

### Requirements

- Windows 10 64-bit or Windows 11 64-bit
- Python 3.10 through 3.14
- *Wings Over Flanders Fields: Between Heaven & Hell II*

### Install

```powershell
git clone https://github.com/Malboro66/woff-mate.git
cd woff-mate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

For development dependencies:

```powershell
pip install -e ".[dev]"
```

### Configure

Create a local configuration from the tracked example:

```powershell
Copy-Item config.example.json config.json
```

Then update `watch_paths` and `export_path` for your WOFF installation. Local `config.json` files, databases, logs, virtual environments, caches, and build outputs are intentionally not versioned.

### Run

```powershell
woff-watchdog
```

Useful commands:

```powershell
woff-watchdog --help
woff-watchdog --version
woff-watchdog --discover
woff-watchdog --parse-file "C:\path\to\Pilot1Dossier.txt"
woff-report
```

## How It Works

```text
WOFF
  │
  ▼
Campaign files
  │
  ▼
Watchdog / stable snapshot ingestion
  │
  ▼
Parsers and normalization
  │
  ▼
Campaign engine
  │
  ├── Pilots
  ├── Missions
  ├── Victories
  ├── Wingmen
  ├── RPG state
  └── Diary entries
  │
  ▼
SQLite
  │
  ▼
WoFF Mate presentation layer / future UI
```

WoFF Mate is structured as a modular monolith: one Windows application and one local SQLite database, split into foundation, domain, persistence, platform, ingestion, application, presentation, and governance responsibilities.

## Compatibility

The project targets Windows 10/11 and Python `>=3.10,<3.15`. CI currently exercises Python 3.10 and 3.14 on Linux, performs type checking with Pyright, and runs a Windows smoke/build path with Python 3.10.

WOFF format support is limited to behavior confirmed by sanitized samples and regression tests. See [compatibility and safe reporting](docs/compatibility.md) for the current support boundaries.

## Project Status

🚧 **Active development**

Core ingestion, persistence, campaign processing, RPG systems, and engineering quality gates are under active development. The application version is sourced from `woff/version.py`; schema and configuration format versions evolve independently.

Current work and planned features are tracked in the [WoFF Mate Development Project](https://github.com/users/Malboro66/projects/1) and in [GitHub Issues](https://github.com/Malboro66/woff-mate/issues).

## Documentation

- [Architecture](docs/architecture/modular-monolith.md)
- [Executable project graph](docs/architecture/project-graph.yaml)
- [UI toolkit ADR](docs/architecture/adr-ui-toolkit.md)
- [Read-only UI foundation](docs/ui/read-only-foundation.md)
- [Compatibility and safe reporting](docs/compatibility.md)
- [Database migrations and recovery](docs/database-migrations.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Engineering evals](docs/engineering/evals.md)
- [Quality gates](docs/engineering/quality-gates.md)
- [Progressive autonomy](docs/engineering/autonomy.md)

## Development

Install the development dependencies and run the same core checks used by CI:

```powershell
pip install -e ".[dev]"
python scripts/validate_project_graph.py
python -m pytest -q
pyright
```

The GitHub Actions workflow also builds and inspects the Python wheel, imports installed modules, exercises installed entry points, and performs a Windows PyInstaller smoke build.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Contributing

Contributions, bug reports, sanitized compatibility samples, documentation improvements, and focused pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and use the existing issue tracker to coordinate non-trivial changes.

For security-sensitive reports, follow [SECURITY.md](SECURITY.md) rather than opening a public issue.

## License

WoFF Mate is released under the [MIT License](LICENSE).

## Disclaimer

WoFF Mate is an independent, community-developed companion application and is not affiliated with or endorsed by OBD Software.

*Wings Over Flanders Fields*, related names, trademarks, and game assets belong to their respective owners.
