<img src="icon.png" alt="WOFF MATE LOGO">
WoFF Mate

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
- 👨‍✈️ **Pilot tracking** — keeps persistent career records separate with Dossier-backed pilot-slot identity; display names are not treated as unique IDs.
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
- *Wings Over Flanders Fields: Between Heaven & Hell II* (WOFF BH&H II)

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
woff-query --format json
woff-report --config config.json
```

All three installed commands use the same process contract: `0` means success,
`1` means a runtime failure, and `2` means invalid input, configuration, or a
missing required resource. JSON, CSV, and Markdown query output is written only
to stdout; diagnostics are written to stderr. See the
[command-line contracts](docs/command-line-contracts.md) for selectors, empty
results, report generation, and export-backup behavior.

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

### Career identity boundary

Stable `Pilot{N}Dossier.txt` snapshots establish the current career for a pilot
slot. `Log`, `Claims`, and `Squads` files may update that career only when the
simultaneously observed Dossier digest matches the stored binding. Confirmed
Dossier deletion or move-away releases only that campaign-root/slot binding;
historical careers remain queryable, and surviving slots are never renumbered.
Reuse after confirmed vacancy creates a separate career ID even for the same
display name. A different name also starts a new career in an occupied slot.
Temporary replacement and unavailable or incompletely scanned roots do not
prove vacancy. Same-name replacement without an observed vacancy remains the
separate evidence gap tracked by #87. See
[vacancy reconciliation](docs/troubleshooting.md#pilot-slot-vacancy) for recovery
and source-presence semantics.

Parsed campaign XML and `Mission.log` remain available to parser/reporting
workflows, but the live persistence path rejects them when they cannot supply
a supported career identity.

## Compatibility

The project targets Windows 10/11 and Python `>=3.10,<3.15`. CI currently exercises Python 3.10 and 3.14 on Linux, performs type checking with Pyright, and runs a Windows smoke/build path with Python 3.10.

WOFF BH&H II format support is limited to behavior confirmed by sanitized samples and regression tests. The exact WOFF build represented by the current sanitized samples has not yet been confirmed. See [compatibility and safe reporting](docs/compatibility.md) for the current support boundaries.

<!--
Compatibility-contract anchors retained for the existing documentation consistency test.
These phrases are intentionally non-rendered; the user-facing README is English.
Python da versão 3.10 até a 3.14
Windows 10 de 64 bits
Windows 11 de 64 bits
amostras sanitizadas
versão exata do WoFF ainda não foi confirmada
-->

## Project Status

🚧 **Active development**

Core ingestion, persistence, campaign processing, RPG systems, and engineering quality gates are under active development. The application version is sourced from `woff/version.py`; schema and configuration format versions evolve independently.

Current work and planned features are tracked in the [WoFF Mate Development Project](https://github.com/users/Malboro66/projects/1) and in [GitHub Issues](https://github.com/Malboro66/woff-mate/issues).

## Documentation

- [Architecture](docs/architecture/modular-monolith.md)
- [Executable project graph](docs/architecture/project-graph.yaml)
- [UI toolkit ADR](docs/architecture/adr-ui-toolkit.md)
- [Read-only UI foundation](docs/ui/read-only-foundation.md)
- [Shared screen-state matrix](docs/ui/screen-state-matrix.md)
- [Synthetic UI fixture inventory](woff/tests/fixtures/ui_states/README.md)
- [Published UI V2 prototype](https://woff-mate-ui-v2.pilotohans.chatgpt.site/)
- [UI V2 reference](docs/ui/ui-v2-reference.md)
- [UI V2 visual system](docs/ui/ui-v2-visual-system.md)
- [UI V2 design walkthrough](docs/ui/ui-v2-walkthrough.md)
- [UI V2 published-site audit](docs/ui/ui-v2-rendered-audit.md)
- [UI V2 executable conformance evidence](docs/ui/evidence/ui-v2-site-2026-09-01-audit-4/README.md)
- [Compatibility and safe reporting](docs/compatibility.md)
- [Database migrations and recovery](docs/database-migrations.md)
- [Command-line contracts](docs/command-line-contracts.md)
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
