from database.db import SessionLocal

from database.raw_models import (
    GerritChange
)

from database.kpi_models import (
    DeveloperSnapshot,
    TeamSnapshot
)


def save_metric(username, metric_name, metric_value):

    db = SessionLocal()

    db.add(
        DeveloperSnapshot(
            username=username,
            metric_name=metric_name,
            metric_value=float(metric_value)
        )
    )

    db.commit()
    db.close()


def get_developer_metrics(username):

    db = SessionLocal()

    rows = db.query(
        DeveloperSnapshot
    ).filter(
        DeveloperSnapshot.username == username
    ).all()

    db.close()

    return rows

def get_latest_snapshot(username):

    db = SessionLocal()

    snapshot = (
        db.query(DeveloperSnapshot)
        .filter(
            DeveloperSnapshot.username == username
        )
        .order_by(
            DeveloperSnapshot.snapshot_time.desc()
        )
        .first()
    )

    db.close()

    return snapshot

def get_all_developers(start_date=None, end_date=None):
    """
    Get distinct Gerrit change owners.

    Args:
        start_date (datetime, optional): Filter by updated_at >= start_date.
        end_date (datetime, optional): Filter by updated_at <= end_date.

    Returns:
        list: Developer usernames.
    """

    db = SessionLocal()

    query = db.query(GerritChange.owner).distinct()
    if start_date is not None:
        query = query.filter(GerritChange.updated_at >= start_date)
    if end_date is not None:
        query = query.filter(GerritChange.updated_at <= end_date)

    rows = query.all()

    db.close()

    return [r[0] for r in rows]

def upsert_gerrit_change(change):
    """
    Upsert a Gerrit change into the database.
    
    Args:
        change (dict): Change object with keys: id, change_number, project, 
                      owner, status, created_at, updated_at, raw_json
    """

    db = SessionLocal()

    existing = db.get(
        GerritChange,
        change["id"]
    )

    owner_username = change["owner"].get("username", "unknown") if isinstance(change["owner"], dict) else str(change["owner"])

    if existing:
        existing.change_number = change.get("change_number")
        existing.project = change.get("project")
        existing.owner = owner_username
        existing.status = change.get("status")
        existing.created_at = change.get("created_at")
        existing.updated_at = change.get("updated_at")
        existing.raw_json = change.get("raw_json", change)
    else:
        db.add(
            GerritChange(
                change_id=change["id"],
                change_number=change.get("change_number"),
                project=change.get("project"),
                owner=owner_username,
                status=change.get("status"),
                created_at=change.get("created_at"),
                updated_at=change.get("updated_at"),
                raw_json=change.get("raw_json", change)
            )
        )

    db.commit()
    db.close()

def save_snapshot(
    username,
    metrics
):

    db = SessionLocal()

    db.add(
        DeveloperSnapshot(
            username=username,
            metrics_json=metrics
        )
    )

    db.commit()
    db.close()

def get_all_gerrit_changes():
    """
    Get all Gerrit changes from the database.
    
    Returns:
        list: List of raw_json objects for each change
    """

    db = SessionLocal()

    changes = db.query(GerritChange).all()

    db.close()

    return [c.raw_json for c in changes]


def get_all_projects(username=None, start_date=None, end_date=None):
    """
    Get distinct Gerrit project names.
    
    Args:
        username (str, optional): If provided, filter projects by owner username.
        start_date (datetime, optional): Filter by updated_at >= start_date.
        end_date (datetime, optional): Filter by updated_at <= end_date.
    
    Returns:
        list: Project names
    """

    db = SessionLocal()

    query = db.query(GerritChange.project).distinct()
    if username:
        query = query.filter(GerritChange.owner == username)
    if start_date is not None:
        query = query.filter(GerritChange.updated_at >= start_date)
    if end_date is not None:
        query = query.filter(GerritChange.updated_at <= end_date)

    rows = query.all()

    db.close()

    return [r[0] for r in rows]


def get_project_topics(repo, username=None, start_date=None, end_date=None):
    """
    Get distinct topics for a given project.

    Args:
        repo (str): Project name.
        username (str, optional): Filter by owner username.
        start_date (datetime, optional): Filter by updated_at >= start_date.
        end_date (datetime, optional): Filter by updated_at <= end_date.

    Returns:
        list: Sorted list of topic names.
    """

    db = SessionLocal()

    query = db.query(GerritChange.raw_json).filter(
        GerritChange.project == repo
    )

    if username:
        query = query.filter(GerritChange.owner == username)

    if start_date is not None:
        query = query.filter(GerritChange.updated_at >= start_date)

    if end_date is not None:
        query = query.filter(GerritChange.updated_at <= end_date)

    rows = query.all()
    db.close()

    topics = set()
    for row in rows:
        raw = row[0] if isinstance(row, tuple) else row
        topic = raw.get("topic") if isinstance(raw, dict) else None
        topics.add(topic or "untagged")

    return sorted(topics)

def get_gerrit_changes_by_date(start_date, end_date, username=None):
    """
    Get Gerrit changes filtered by date range and optionally by owner username.
    
    Args:
        start_date (datetime): Start date filter
        end_date (datetime): End date filter
        username (str, optional): Filter by owner username. Defaults to None.
    
    Returns:
        list: List of raw_json objects for matching changes
    """

    db = SessionLocal()

    query = db.query(GerritChange).filter(
        GerritChange.updated_at >= start_date,
        GerritChange.updated_at <= end_date
    )

    if username:
        query = query.filter(GerritChange.owner == username)

    changes = query.all()

    db.close()

    return [c.raw_json for c in changes]

def save_team_snapshot(metrics):

    db = SessionLocal()

    db.add(
        TeamSnapshot(
            metrics_json=metrics
        )
    )

    db.commit()
    db.close()