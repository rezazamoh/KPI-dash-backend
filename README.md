# KPI Dash Backend

A backend service for Gerrit-based KPI reporting, raw change storage, and metric data delivery through FastAPI.

## Table of Contents

- [Purpose](#purpose)
- [Main Features](#main-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Technologies and Dependencies](#technologies-and-dependencies)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Data Flow](#data-flow)
- [API Overview](#api-overview)
- [KPI Overview](#kpi-overview)
- [Live Mode vs Offline Mode](#live-mode-vs-offline-mode)
- [Database Overview](#database-overview)
- [Current Limitations and Assumptions](#current-limitations-and-assumptions)
- [Future Improvements](#future-improvements)
- [Development Notes](#development-notes)

## Purpose

This project collects Gerrit change data, computes developer and project-level KPIs, and exposes those metrics through a REST API.

It is designed for teams that want to monitor Gerrit review activity, code review collaboration, and delivery metrics.

## Main Features

- Raw Gerrit change ingestion into SQLite
- Gerrit KPI computation for developers and projects
- Live Gerrit query support via SSH
- Offline querying via persisted database records
- FastAPI endpoints for developer and project metrics
- Frontend-configurable duration windows for KPI distributions
- Snapshot persistence for developer and team KPI data

## System Architecture

The backend is organized into:

- `app.py` for FastAPI application setup
- `api/` for request routers and shared API utilities
- `collectors/` for Gerrit query execution and parsing
- `database/` for SQLAlchemy models and persistence logic
- `jobs/` for data ingestion and KPI refresh scripts
- `kpis/` for metric calculation and graph generation
- `data/` for sample/offline Gerrit JSON data files

## Project Structure

- `app.py` - application entry point and router registration
- `api/developers.py` - developer and project API routes
- `api/team.py` - team graph route implementation
- `api/utils.py` - shared request processing and live/offline selector
- `collectors/gerrit_ssh.py` - Gerrit SSH query builder and JSON parser
- `database/db.py` - SQLite engine and session setup
- `database/init_db.py` - table creation script
- `database/raw_models.py` - ORM model for raw Gerrit changes
- `database/kpi_models.py` - ORM models for KPI snapshots
- `database/crud.py` - persistence helpers for raw and snapshot data
- `jobs/collect_raw.py` - ingestion job for Gerrit changes
- `jobs/refresh_kpis.py` - developer snapshot refresh job
- `jobs/refresh_team_kpi.py` - team graph snapshot refresh job
- `kpis/gerrit_kpis.py` - developer/project KPI computations and graphs

- `data/` - sample Gerrit/Jenkins/Jira JSON fixtures
- `config.py` - hardcoded Gerrit/Jenkins/Jira connection settings
- `requirements.txt` - dependency list

## Technologies and Dependencies

- Python 3.10+ (type union syntax used)
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- Standard library modules: `subprocess`, `json`, `datetime`, `collections`, `statistics`

Dependencies are listed in `requirements.txt`.

## Installation

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

### Gerrit

`config.py` defines Gerrit SSH connection details:

- `GERRIT_HOST`
- `GERRIT_PORT`
- `GERRIT_USER`

This project currently uses direct configuration in `config.py` rather than environment variables.

### Database

The SQLite connection is configured in `database/db.py`:

```python
DATABASE_URL = "sqlite:///metrics.db"
```

Change this file to use a different SQLite path.

### Jenkins and Jira

`.env` defines Jenkins and Jira placeholders.


## Running the Application

For using live mode which is default option, just start from step 5.

1. Create the database tables:

```cmd
python -m database.init_db
```

2. Load raw change data:

```cmd
python -m jobs.collect_raw
```

3. Refresh developer KPI snapshots:

```cmd
python -m jobs.refresh_kpis
```

4. Refresh team KPI snapshot:

```cmd
python -m jobs.refresh_team_kpi
```

5. Start the FastAPI server:

```cmd
uvicorn app:app --reload
```

6. Open API docs:

```text
http://127.0.0.1:8000/docs
```

## Data Flow

### Fetching Gerrit changes

- **Live mode**: `api/utils.py` calls `collectors/gerrit_ssh.fetch_changes(...)`, which builds and runs an SSH `gerrit query` command.
- **Offline mode**: `api/utils.py` calls `database.crud.get_gerrit_changes(...)`, which reads persisted raw changes from SQLite.

### Database storage

- `jobs/collect_raw.py` ingests changes and upserts them into the `gerrit_changes` table.
- `database/crud.py` persists both normalized metadata and the full raw JSON payload.

### KPI calculation

- `kpis/gerrit_kpis.py` computes developer and project metrics from raw Gerrit change objects.
- `jobs/refresh_kpis.py` and `jobs/refresh_team_kpi.py` persist snapshot JSON into `developer_snapshots` and `team_snapshots`.

### API layer

- `api/developers.py` exposes developer/project-related query endpoints.
- `api/utils.py` validates dates and selects the live/offline data source.
- `app.py` mounts routes and exposes root/health endpoints.

## API Overview

| Path | Method | Description | Query Parameters |
|---|---|---|---|
| `/` | GET | Health/status message | none |
| `/developers` | GET | List all developer usernames available in the selected dataset | `start_date`, `end_date`, `live` |
| `/developers/{username}` | GET | Developer KPI summary for a specific username | `repo`, `topic`, `start_date`, `end_date`, `group_by_repo`, `group_by_topic`, `live` |
| `/developers/{username}/topics` | GET | List all topics of a specific developer | `repo`, `start_date`, `end_date`,`live` |
| `/projects` | GET | List all projects available in the selected dataset | `start_date`, `end_date`, `live` |
| `/projects/{project:path}` | GET | Project-level developer metrics for a specific project | `username`, `topic`, `start_date`, `end_date`, `live` |
| `/api/settings` | GET | Read global KPI display settings | none |
| `/api/settings` | PATCH | Update global KPI display settings | JSON body |

### Parameter behavior

- `start_date` and `end_date` must be supplied together or omitted.
- `repo`, `username`, and `topic` may be provided as repeated query parameters (e.g. looking up a developer's performance through several repos).
- `live=true` forces Gerrit SSH query execution instead of SQLite lookups.
- `group_by_repo` and `group_by_topic` flags are used to see developers performance separated by repos or topics along side the overall performance. 
- `duration_windows` controls lead-time and patchset-gap distributions. Set `use_duration_windows` to `false` to temporarily use automatic bucketing without deleting the saved windows. The first `min` and final `max` may be `null` for open-ended ranges.

Example settings body:

```json
{
	"use_duration_windows": true,
	"duration_windows": [
		{"min": 0, "max": 3600},
		{"min": 3600, "max": 86400},
		{"min": 86400, "max": null}
	]
}
```

## KPI Overview

| KPI | What it represents |
|---|---|
| `change_count` | Number of Gerrit changes owned by the developer |
| `changes_by_status_per_repo` | Counts of changes grouped by Gerrit status and project |
| `average_patchsets` | Average number of patch sets per owned change |
| `review_requests_received` | Review requests received by a developer, with reviewer counts |
| `review_requests_sent` | Review requests sent by a developer when acting as reviewer |
| `comments_received` | Comments received on a developer's owned changes |
| `comments_sent` | Comments authored by a developer on others' changes |
| `lead_time` | Lead time from change creation to final update for merged changes |
| `reviewer_response_time` | Time between reviewer assignment and first reviewer comment |
| `build_failure_rate` | Failure rate derived from Jenkins-style Gerrit vote comments |

Live Mode vs Offline Mode

- **Live mode**: Uses Gerrit SSH and Rest query through `collectors/gerrit_ssh.py` and `collectors/gerrit_rest.py`.
- **Offline mode**: Uses stored raw change records from SQLite.

## Database Overview

| Table | Purpose |
|---|---|
| `gerrit_changes` | Raw Gerrit change records and metadata |
| `developer_snapshots` | Persisted developer KPI snapshot JSON |

`gerrit_changes` stores normalized columns such as `project`, `author`, `status`, `created_at`, `updated_at`, and `raw_json`.

## Current Limitations and Assumptions

- Jenkins and Jira settings exist in `config.py` but are not consumed.
- There is no authentication or API access control.
- SQLite is the only supported database backend.

## Future Improvements

- Add a formal test suite for API routes and KPI calculations.
- Support configurable database backends beyond SQLite.
- Improve input validation and error handling for query parameters.
- Replace hardcoded credentials with secure secret management.

## Development Notes

- Use `python -m database.init_db` before ingesting data.
- Run `python -m jobs.collect_raw` to populate raw change data.
- `uvicorn app:app --reload` starts the API server.
- The current data ingestion path relies on JSON fixtures rather than live Gerrit SSH by default.
- The `collectors/gerrit_ssh.py` implementation can be used for live Gerrit queries if the SSH config is valid.
