
# HeyStat

**HeyStat** is a web-based statistical analysis platform, forked from [jamovi](https://www.jamovi.org).

## About

HeyStat provides:
- ✅ Web-based statistical analysis (no installation required)
- ✅ Familiar interface for SPSS users
- ✅ Vietnamese-friendly deployment
- ✅ Educational focus for Vietnamese institutions

**Built on jamovi 2.7.30** - See [FORK_NOTICE.md](docs/FORK_NOTICE.md) for attribution.

## Quick Access

🌐 **Live Instance**: https://heystat.pedu.vn

## Features

- Descriptive statistics, T-tests, ANOVA, regression
- Extra normality/variance tests (Kolmogorov-Smirnov, Anderson-Darling, Bartlett) via the [moretests](https://github.com/jonathon-love/moretests) module
- Data visualization and plotting
- CSV/SPSS/SAS file import
- Real-time analysis updates
- R syntax generation

## For Users

### Access HeyStat
Visit: https://heystat.pedu.vn

No installation required - works in any modern browser (Chrome, Firefox, Safari, Edge).

### Documentation
- [HeyStat documentation index](docs/README.md) — current vs historical docs
- Based on jamovi - see [jamovi user manual](https://www.jamovi.org/user-manual.html)
- All jamovi analyses and features are available

## For Developers

### Quick Start with Docker

```bash
# Clone repository
git clone https://github.com/phucdhh/HeyStat.git
cd HeyStat
git submodule update --init --recursive

# Build and run
docker compose --profile main build
docker compose --profile main up
```

Access at: http://127.0.0.1:42337

## dev mode

jamovi can be run with a vite dev server serving the client files as follows:

```bash
docker compose --profile dev up
```

For dev mode with hot-reload:

```bash
poetry install
```

If poetry can't locate a Python executable with the correct version, ensure
that you have the correct version installed and run these commands to force
poetry to use it:

```bash
poetry env use PATH_TO_PYTHON_EXECUTABLE
poetry install
```

## Usage

### Deployment Configurations

The current production deployment is a **Linux LXC (amd64)**:
- **HeyStat/jamovi** in Docker on port `42337`
- **Classroom LMS** (FastAPI + PostgreSQL + Redis + Celery) on port `8080`
- **Nginx** in front of both, with `/classroom/` and `/api/` routes
- **Cloudflare** for public HTTPS access

Historical Mac Mini deployment notes are kept for reference only:
- [Documentation index](docs/README.md) — current vs historical docs
- [Mac Deployment Guide (historical)](docs/README_MAC_DEPLOYMENT.md)
- [Auto-Start Configuration (historical)](docs/AUTOSTART_FIX.md)

### Access Key for Security

HeyStat can be protected with an access key via `JAMOVI_ACCESS_KEY` environment variable.

- For local development: Set `JAMOVI_ACCESS_KEY=''` (empty) in `docker-compose.yaml`
- For production: Set a strong access key
- To disable for testing: Set `JAMOVI_DISABLE_ACCESS_KEY=1` (NOT for production)

## Activate the virtual environment

```bash
poetry shell
```

## Developer section

### Usage - Poetry

```bash
poetry shell  # to activate the virtual environment
poetry run COMMAND  # run a command in the venv without first activating it
poetry add DEPENDENCY  # add a production dependency
poetry add --group=dev DEVDEPENDENCY  # add a dev dependency
poetry add --group=GROUPNAME DEPENDENCY  # add a dependency to another group

poetry lock  # update the lock file
poetry install  # install dependencies from the lock file
poetry install --sync  # also remove untracked dependencies from venv
poetry update  # lock & install
poetry update --sync  # lock & install --sync
```

For more information about Poetry, see the [Poetry docs][poetry-docs].

### Usage - Poe

We use `poe` to run tasks that simplify running things like tests, QA-tools, and
docker. This is similar to how one might use `make` to simplify running commands
with arguments or combinations of commands.

You can run `poe` in two ways:

```bash
# By first activating the virtual environment
poetry shell
poe TASKNAME [OPTIONAL_ADDITIONAL_ARGS]

# By using `poetry run` without activing the environment
poetry run poe TASKNAME [OPTIONAL_ADDITIONAL_ARGS]
```

For example, to run all tools that reformat code, you can run:

```bash
poetry shell
poe reformat

# or
poetry run poe reformat
```

For a list of all the available tasks, run `poe --help` or look at the task
definitions in [`pypoetry.toml`](pyproject.toml).

For more information about Poe the Poet, look at the [Poe docs][poe-docs].


## Testing

Tests can be run with:

```bash
poe tests
```

## Classroom LMS
Xem [`classroom/`](./classroom/) — module dạy học độc lập, không phải một phần của Jamovi upstream.

# VSCode

If you're using VSCode it's recommended to install the following extensions to make python development easier:

- ms-python.debugpy
- ms-python.pylint
- ms-python.python
- ms-python.vscode-pylance
- charliermarsh.ruff


### Configure virtual environment for VSCode

You can [configure the interpreter path for the workspace](https://code.visualstudio.com/docs/python/environments#_select-and-activate-an-environment) so that you don't have to manually activate the terminal every time you open a terminal.

You can find the path to the python interpreter associated with the virtual environment easily by:

```bash
# Activate the environment
poetry shell
# Find the python path for this environment
where python
```

## Key Differences from jamovi

### Deployment
- **Linux LXC (amd64)** production deployment
- Custom **port configuration** (`42337` for jamovi, `8080` for the LMS API)
- **Nginx reverse proxy** with WebSocket support and an auth gate
- **Cloudflare** integration for public HTTPS access

### Branding
- Application name: **HeyStat** (was: jamovi)
- Custom domain: https://heystat.pedu.vn
- Vietnamese localization focus

### Infrastructure
- **Docker Compose**: jamovi core + Classroom LMS
- **PostgreSQL**, **Redis**, **Celery worker/beat** for the LMS
- **Isolated Documents folder** for user data
- **Production-ready** security configuration

See [FORK_NOTICE.md](docs/FORK_NOTICE.md) for complete fork information.

## License

HeyStat is licensed under **AGPL3/GPL2+**, same as jamovi.

```
Copyright (C) 2025 HeyStat Team
Copyright (C) 2016-2024 The jamovi team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

See [LICENSE.md](LICENSE.md) for full license text.

## Acknowledgments

HeyStat is built on [jamovi](https://www.jamovi.org) by The jamovi team.

We are grateful to:
- **The jamovi team** for creating excellent open-source statistical software
- **The R Project** and all R package developers
- **The open-source community** for tools and libraries

## Links

- **jamovi**: https://www.jamovi.org (original project)
- **jamovi Source**: https://github.com/jamovi/jamovi
- **jamovi Community**: https://forum.jamovi.org
- **HeyStat Live**: https://heystat.pedu.vn

---

**HeyStat** - A fork of jamovi for Vietnamese educational institutions
