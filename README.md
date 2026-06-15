## KPI-dash-backend

# 1. Create & Activate Virtual Environment

```cmd
python -m venv venv
```

```cmd
venv\Scripts\activate
```

Verify:

```cmd
python --version
```

---

# 2. Install Dependencies

```cmd
pip install fastapi uvicorn sqlalchemy pydantic
```

(Optional, if you're using Gerrit/Jira APIs later)

```cmd
pip install requests
```

Generate requirements:

```cmd
pip freeze > requirements.txt
```

---

# 3. Initialize Database

From project root:

```cmd
python -m database.init_db
```

Expected:

```text
Database created
```

This creates:

```text
metrics.db
```

---

# 4. Load Raw Gerrit Data

If your export file is:

```text
data\gerrit.json
```

Run:

```cmd
python -m jobs.collect_raw
```

Expected:

```text
Loaded XXX changes
```

Verify in DB:

```sql
SELECT COUNT(*) FROM gerrit_changes;
```

---

# 5. Generate KPI Snapshots

Run:

```cmd
python -m jobs.refresh_kpis
```

Expected:

```text
Saved XXX developer snapshots
```

Verify:

```sql
SELECT username, metrics_json
FROM developer_snapshots
LIMIT 5;
```

---

# 6. Start FastAPI

From project root:

```cmd
uvicorn app:app --reload
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

---

# 7. Open API Docs

Browser:

```text
http://127.0.0.1:8000/docs
```

You should see your endpoints (whatever you've implemented so far, e.g. `/health`, `/developers`, `/developers/{username}`).

---

# 8. Useful Development Commands

Recreate DB from scratch:

```cmd
del metrics.db
python -m database.init_db
```

Reload raw data:

```cmd
python -m jobs.collect_raw
```

Recalculate KPIs:

```cmd
python -m jobs.refresh_kpis
```

Start server:

```cmd
uvicorn app:app --reload
```

---

# Expected Project Layout

```text
KPI-dash-backend/
│
├── app.py
│
├── api/
│   ├── __init__.py
│   ├── developers.py
│   └── team.py
│
├── database/
│   ├── __init__.py
│   ├── db.py
│   ├── crud.py
│   ├── raw_models.py
│   ├── kpi_models.py
│   ├── global_models.py
│   └── init_db.py
│
├── jobs/
│   ├── __init__.py
│   ├── collect_raw.py
│   ├── refresh_kpis.py
│   └── refresh_team_kpis.py
│
├── kpis/
│   ├── __init__.py
│   ├── gerrit_kpis.py
│   └── team_kpis.py
│
├── clients/
│   ├── __init__.py
│   └── file_loader.py
│
├── data/
│   └── gerrit.json
│
├── metrics.db
│
├── requirements.txt
│
└── venv/
```

Once all of that runs cleanly, the next backend milestone is:

* `GET /developers`
* `GET /developers/{username}`
* `GET /team/graph`
* Implementing the real `review_response_time` KPI from Gerrit reviewer activity data.
