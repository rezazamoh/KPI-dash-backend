from database.db import SessionLocal

from database.raw_models import (
    GerritChange
)

from database.kpi_models import (
    DeveloperSnapshot,
    TeamSnapshot
)

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

def get_gerrit_changes(
    start_date=None,
    end_date=None,
    owner=None,
    reviewer=None,
    commenter=None,
    project=None,
    topic=None,
):
    """
    Get Gerrit changes from the database with optional filters.

    Args:
        start_date (datetime, optional): Filter by updated_at >= start_date.
        end_date (datetime, optional): Filter by updated_at <= end_date.
        owner (str, optional): Filter by Gerrit owner username.
        project (str, optional): Filter by Gerrit project.
        topic (str, optional): Filter by Gerrit topic.

    Returns:
        list: List of raw_json objects for matching changes.
    """

    def _as_list(value):
        if value is None:
            return None

        if isinstance(value, str):
            return [value]

        return value

    db = SessionLocal()
    query = db.query(GerritChange)

    owner = _as_list(owner)
    reviewer = _as_list(reviewer)
    project = _as_list(project)
    topic = _as_list(topic)

    if start_date is not None:
        query = query.filter(GerritChange.updated_at >= start_date)
    if end_date is not None:
        query = query.filter(GerritChange.updated_at <= end_date)
    if owner:
        query = query.filter(GerritChange.owner.in_(owner))
    if project:
        query = query.filter(GerritChange.project.in_(project))

    rows = query.all()
    db.close()

    results = []
    for row in rows:
        raw = row.raw_json

        if not isinstance(raw, dict):
            continue

        # topic filter
        if topic:
            change_topic = raw.get("topic") or "untagged"

            if change_topic not in topic:
                continue

        if reviewer:

            reviewers = {
                r.get("username")
                for r in raw.get("allReviewers", [])
                if r.get("username")
            }

            if not reviewers.intersection(reviewer):
                continue

        if commenter:
            found = False

            for comment in raw.get("comments", []):

                commenter_user = comment.get("reviewer")

                if not commenter_user:
                    continue

                if commenter_user.get("username") == commenter:
                    found = True
                    break

            if not found:
                continue
            
        results.append(raw)

    return results

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

def save_team_snapshot(metrics):

    db = SessionLocal()

    db.add(
        TeamSnapshot(
            metrics_json=metrics
        )
    )

    db.commit()
    db.close()