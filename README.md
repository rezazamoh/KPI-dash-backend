# KPI-dash-backend

A FastAPI backend for Gerrit-based KPI reporting.

## 1. Setup

Create and activate a Python virtual environment:

```cmd
python -m venv venv
venv\Scripts\activate
```

Install project dependencies:

```cmd
pip install -r requirements.txt
```

## 2. Configure Gerrit

Update `config.py` with your Gerrit SSH settings:

```python
GERRIT_HOST = "your.gerrit.host"
GERRIT_PORT = 29418
GERRIT_USER = "your_user"
```

## 3. Initialize the database

From the project root:

```cmd
python -m database.init_db
```

Expected output:

```text
Database created
```

This creates the SQLite database file used by the backend.

## 4. Collect Gerrit changes

The system now loads Gerrit changes via SSH, not from a static JSON export.

Run:

```cmd
python -m jobs.collect_raw
```

This fetches changes from the last 30 days by default and stores them in the database.

To load a custom time window:

```cmd
python -m jobs.collect_raw 2025-01-01 2025-12-31
```

## 5. Refresh KPI snapshots

Once raw data is in the database, generate KPI snapshots:

```cmd
python -m jobs.refresh_kpis
```

This writes developer KPI snapshots to the database for API consumption.

## 6. Run the API server

Start FastAPI with Uvicorn:

```cmd
uvicorn app:app --reload
```

Open API docs at:

```text
http://127.0.0.1:8000/docs
```

## 7. Available API endpoints

### Health

- `GET /health`

### Developers

- `GET /developers`
  - Query params: `start_date`, `end_date`
  - Defaults to full history when date filters are omitted

- `GET /developers/{username}`

- `GET /developers/performance/{username}`
  - Query params:
    - `repo` (project name)
    - `topic`
    - `start_date`
    - `end_date`
  - Default behavior is full history when dates are omitted

### Projects

- `GET /projects`
  - Query params: `username`, `start_date`, `end_date`

- `GET /projects/performance/{project:path}`
  - Query params: `username`, `topic`, `start_date`, `end_date`, `live`

### Team

- `GET /team/graph`

## 8. Notes

- The `/projects/{repo}/topics` endpoint was removed for now.
- Date filters are optional and must be provided together: both `start_date` and `end_date`, or neither.
- `jobs.collect_raw` now uses `collectors/gerrit_ssh.py` to fetch Gerrit changes via SSH.

## 9. Useful commands

Recreate the database from scratch:

```cmd
del metrics.db
python -m database.init_db
```

Reload raw Gerrit data:

```cmd
python -m jobs.collect_raw
```

Recalculate KPI snapshots:

```cmd
python -m jobs.refresh_kpis
```

Start the server:

```cmd
uvicorn app:app --reload
```

## 10. Current project layout

```text
KPI-dash-backend/
├── app.py
├── api/
│   ├── __init__.py
│   ├── developers.py
│   └── team.py
├── collectors/
│   ├── __init__.py
│   └── gerrit_ssh.py
├── database/
│   ├── __init__.py
│   ├── crud.py
│   ├── db.py
│   ├── global_models.py
│   ├── init_db.py
│   ├── kpi_models.py
│   └── raw_models.py
├── jobs/
│   ├── __init__.py
│   ├── collect_raw.py
│   ├── refresh_kpis.py
│   └── refresh_team_kpi.py
├── kpis/
│   ├── __init__.py
│   ├── gerrit_kpis.py
│   └── team_kpis.py
├── clients/
│   ├── __init__.py
│   ├── file_loader.py
│   ├── gerrit.py
│   ├── jenkins.py
│   └── jira.py
├── config.py
├── requirements.txt
└── README.md
```
