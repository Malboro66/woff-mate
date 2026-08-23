# Security Policy

## Supported Versions

WoFF Mate is under active development. Security fixes are applied to the current development line unless a release-specific support policy is announced later.

## Reporting a Vulnerability

Please do not report security vulnerabilities in public GitHub Issues.

Use GitHub's private vulnerability reporting feature for this repository when it is available. If private reporting is not available, contact the maintainer through a private GitHub-supported channel rather than posting exploit details publicly.

Include enough information to reproduce and assess the issue, such as:

- affected version or commit
- affected platform
- reproduction steps
- expected and observed behavior
- impact assessment
- relevant sanitized logs or proof-of-concept details

Do not include personal campaign data, credentials, private filesystem paths, or other sensitive information unless it is essential and transmitted through a private reporting channel.

## Scope

Security-relevant areas include, but are not limited to:

- file ingestion and path handling
- configuration parsing
- SQLite persistence and migrations
- packaged Windows executables
- dependency or supply-chain issues
- unintended writes to WOFF or user data

## Disclosure

Please allow reasonable time for investigation and remediation before public disclosure. Once a fix is available, the project may publish a security advisory with appropriate technical detail and upgrade guidance.
