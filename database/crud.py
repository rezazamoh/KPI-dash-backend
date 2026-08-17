from datetime import datetime
from database.db import SessionLocal

from database.raw_models import (
    GerritChange,
    JiraIssue
)

from database.kpi_models import (
    DeveloperSnapshot,
    TeamSnapshot
)

def upsert_gerrit_change(change):
    """
    Upsert a Gerrit change into the database.
    
    Args:
        change (dict): Raw Gerrit change object.
    """

    db = SessionLocal()

    existing = db.get(
        GerritChange,
        change["id"]
    )

    owner_username = change["owner"].get("username", "unknown") if isinstance(change["owner"], dict) else str(change["owner"])
    change_number = change.get("number")
    created_at = datetime.fromtimestamp(change.get("createdOn")) if change.get("createdOn") else None
    updated_at = datetime.fromtimestamp(change.get("lastUpdated")) if change.get("lastUpdated") else None
    raw_json = change.get("raw_json", change)

    if existing:
        existing.change_number = change_number
        existing.project = change.get("project")
        existing.owner = owner_username
        existing.status = change.get("status")
        existing.created_at = created_at
        existing.updated_at = updated_at
        existing.raw_json = raw_json
    else:
        db.add(
            GerritChange(
                change_id=change["id"],
                change_number=change_number,
                project=change.get("project"),
                owner=owner_username,
                status=change.get("status"),
                created_at=created_at,
                updated_at=updated_at,
                raw_json=raw_json
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

def upsert_jira_issue(issue):
    db = SessionLocal()

    fields = issue.get("fields", {})

    issue_key = issue["key"]

    assignee = fields.get("assignee")
    assignee = assignee.get("name") if assignee else None

    status = fields.get("status")
    status = status.get("name") if status else None

    issue_type = fields.get("issuetype")
    issue_type = issue_type.get("name") if issue_type else None

    priority = fields.get("priority")
    priority = priority.get("name") if priority else None

    project = fields.get("project")
    project = project.get("key") if project else None

    created_at = (
        datetime.fromisoformat(
            fields["created"].replace("Z", "+00:00")
        )
        if fields.get("created")
        else None
    )

    updated_at = (
        datetime.fromisoformat(
            fields["updated"].replace("Z", "+00:00")
        )
        if fields.get("updated")
        else None
    )

    resolved_at = (
        datetime.fromisoformat(
            fields["resolutiondate"].replace("Z", "+00:00")
        )
        if fields.get("resolutiondate")
        else None
    )

    existing = db.get(JiraIssue, issue["id"])

    if existing:
        existing.issue_key = issue_key
        existing.project = project
        existing.summary = fields.get("summary")
        existing.status = status
        existing.issue_type = issue_type
        existing.assignee = assignee
        existing.priority = priority
        existing.created_at = created_at
        existing.updated_at = updated_at
        existing.resolved_at = resolved_at
        existing.raw_json = issue

    else:
        db.add(
            JiraIssue(
                issue_id=issue["id"],
                issue_key=issue_key,
                project=project,
                summary=fields.get("summary"),
                status=status,
                issue_type=issue_type,
                assignee=assignee,
                priority=priority,
                created_at=created_at,
                updated_at=updated_at,
                resolved_at=resolved_at,
                raw_json=issue,
            )
        )

    db.commit()
    db.close()

def get_jira_issues(
    start_date=None,
    end_date=None,
    project=None,
    boards=None,
    issue_key=None,
):
    def _as_list(value):
        if value is None:
            return None

        if isinstance(value, str):
            return [value]

        return value

    project = _as_list(project)
    boards = _as_list(boards)
    issue_key = _as_list(issue_key)

    db = SessionLocal()
    query = db.query(JiraIssue)

    if start_date is not None:
        query = query.filter(
            JiraIssue.updated_at >= start_date
        )

    if end_date is not None:
        query = query.filter(
            JiraIssue.updated_at <= end_date
        )

    if project:
        query = query.filter(
            JiraIssue.project.in_(project)
        )

    if issue_key:
        query = query.filter(
            JiraIssue.issue_key.in_(issue_key)
        )

    rows = query.all()
    db.close()

    results = []

    for row in rows:
        raw = row.raw_json

        if not isinstance(raw, dict):
            continue

        results.append(raw)

    return results

def get_jira_projects():
    db = SessionLocal()

    rows = (
        db.query(
            JiraIssue.project
        )
        .filter(JiraIssue.project.isnot(None))
        .distinct()
        .all()
    )

    db.close()

    return [
        {"key": row.project}
        for row in rows
    ]