[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh-CN.md) | [Español](README.es.md) | [اردو](README.ur-pk.md)

# Himmel Hermes ☀️

> A privacy-safe, reproducible downstream distribution of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).

Himmel applies a small, public downstream layer to a pinned, clean Hermes Agent source tree. It preserves the upstream agent while strengthening behavior used in long-running Telegram and gateway deployments, including quota protection, progress and approval presentation, reply scoping, cleanup, restart handling, routing exclusions, and Honcho identity refreshes.

This repository is not a copy of a personal Hermes environment. It contains the complete runnable source tree reconstructed from the identified upstream baseline plus the public downstream changes. It excludes private profiles, credentials, conversations, runtime databases, and raw local provenance patches.

## Downstream scope

Himmel adds or strengthens:

1. fail-closed included-plan quota protection;
2. bounded persona progress and status presentation;
3. allowlisted gateway restart brokering and systemd handling;
4. reply context bounded to the current session;
5. Telegram rich-message policy integration;
6. turn-scoped progress and media cleanup;
7. explicit Telegram group-routing exclusions;
8. structured, localized human-approval UI; and
9. fresh-read Honcho identity cache invalidation.

See [`.himmel/PATCHSET.md`](.himmel/PATCHSET.md) for the concise downstream scope and [`.himmel/UPSTREAM.json`](.himmel/UPSTREAM.json) for the exact upstream identity.

## Install from source

### Requirements

- Python `3.11`–`3.13` (the package requires `>=3.11,<3.14`)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

Linux, macOS, or WSL2:

```bash
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv/bin/hermes
```

Windows PowerShell:

```powershell
git clone https://github.com/Bum-Boo/Himmel.git
cd Himmel
uv sync --locked --extra all
.venv\Scripts\hermes.exe
```

Configure your provider credentials locally after installation. Do not commit `.env` files, API keys, tokens, cookies, or credential files.

The official Hermes installation scripts install the upstream distribution, not Himmel. To run Himmel, clone this repository and use the source installation above. Wheel and source-distribution builds are intentionally unsupported outside the repository’s Nix build path; editable `uv sync` installs are supported.

The source tree retains the upstream Windows installer at `scripts/install.ps1` for compatibility and testing. That script follows the upstream installer contract; it is not the recommended Himmel installation path. Use the pinned source workflow above when installing Himmel.

## Getting started

Run these through `.venv/bin/hermes` on POSIX systems or `.venv\Scripts\hermes.exe` on Windows:

```text
hermes                 Start the interactive agent
hermes --tui           Start the modern terminal UI
hermes setup           Run the setup wizard
hermes model           Configure the model and provider
hermes tools           Configure tools and toolsets
hermes gateway setup   Configure messaging platforms
hermes gateway start   Start the messaging gateway
hermes doctor          Diagnose the installation
hermes --help           Show the current command reference
```

User settings belong in `~/.hermes/config.yaml`; `~/.hermes/.env` is for secrets. Upstream documentation is available at [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/). Some documentation describes upstream installation and release behavior, so use this README’s source-install instructions for Himmel.

## Release status

| Item | Value |
|---|---|
| Himmel version | `2026.08.1-preview.1` |
| Channel | **Public Preview** |
| Upstream tag | `v2026.8.18` |
| Upstream peeled commit | `e624e9fde561e1add9388384012b295fde669ade` |
| Python package metadata | `hermes-agent` `0.20.4` |
| Focused downstream tests | `230 passed` |
| Honcho regression | `25 passed` in each of 3 fresh processes |
| Tooling tests | `64 passed` |
| Full suite | `34,607 passed, 12 failed, 308 skipped` |

Known upstream or platform test failures remain. This release is therefore a public preview for users who review it before installation, not an automatic production promotion. The machine-readable record is [`HIMMEL_RELEASE.json`](HIMMEL_RELEASE.json).

## Privacy and publication boundary

This public repository excludes:

- personal profiles, SOUL files, memory, sessions, and message content;
- API keys, credentials, cookies, tokens, and `.env` files;
- cron history and personal automation state;
- Kanban databases and gateway runtime state;
- personal home paths, Telegram user IDs, and private vault paths; and
- raw private patch provenance.

It includes runnable source, tests, the retained MIT license, the upstream identity record, and public downstream code.

## Upstream acknowledgement and license

Himmel is an independent downstream distribution. It is not an official Nous Research product or release and is not endorsed by Nous Research.

- Upstream project: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- Upstream documentation: [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)
- Downstream notice: [HIMMEL_NOTICE.md](HIMMEL_NOTICE.md)
- License: [MIT](LICENSE)

The MIT license governs legal reuse and redistribution; follow its copyright-and-permission-notice condition as stated in [`LICENSE`](LICENSE). Separately, as a courtesy—not an additional license requirement—please mention [@Bum-Boo](https://github.com/Bum-Boo) and the [original Himmel repository](https://github.com/Bum-Boo/Himmel) when adapting or sharing this downstream work.
