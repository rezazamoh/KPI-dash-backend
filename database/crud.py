from datetime import datetime
from database.db import SessionLocal
from sqlalchemy.orm import selectinload
from database.raw_models import (
    GerritChange,
    JiraIssue,
    Team, TeamMember,TeamDefaultProject,
    Dev,Project
)

from database.kpi_models import (
    DeveloperSnapshot,
    TeamSnapshot,
    AppSettings,
)

_UNSET = object()


def get_app_settings():
    db = SessionLocal()

    try:
        settings = db.get(AppSettings, 1)

        if settings is None:
            return {
                "duration_windows": None,
                "use_duration_windows": True,
                "patchset_windows": None,
                "use_patchset_windows": True,
            }

        return {
            "duration_windows": settings.duration_windows,
            "use_duration_windows": settings.use_duration_windows,
            "patchset_windows": settings.patchset_windows,
            "use_patchset_windows": settings.use_patchset_windows,
        }
    finally:
        db.close()


def update_app_settings(
    duration_windows=_UNSET,
    use_duration_windows=None,
    patchset_windows=_UNSET,
    use_patchset_windows=None,
):
    db = SessionLocal()

    try:
        settings = db.get(AppSettings, 1)

        if settings is None:
            settings = AppSettings(
                id=1,
                duration_windows=(
                    None
                    if duration_windows is _UNSET
                    else duration_windows
                ),
                use_duration_windows=(
                    True
                    if use_duration_windows is None
                    else use_duration_windows
                ),
                patchset_windows=(
                    None
                    if patchset_windows is _UNSET
                    else patchset_windows
                ),
                use_patchset_windows=(
                    True
                    if use_patchset_windows is None
                    else use_patchset_windows
                ),
            )
            db.add(settings)
        else:
            if duration_windows is not _UNSET:
                settings.duration_windows = duration_windows

            if use_duration_windows is not None:
                settings.use_duration_windows = use_duration_windows

            if patchset_windows is not _UNSET:
                settings.patchset_windows = patchset_windows

            if use_patchset_windows is not None:
                settings.use_patchset_windows = use_patchset_windows

        db.commit()
        db.refresh(settings)

        return {
            "duration_windows": settings.duration_windows,
            "use_duration_windows": settings.use_duration_windows,
            "patchset_windows": settings.patchset_windows,
            "use_patchset_windows": settings.use_patchset_windows,
            "updated_at": settings.updated_at,
        }
    finally:
        db.close()

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
    status=None,
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
    status = _as_list(status)

    if start_date is not None:
        query = query.filter(GerritChange.updated_at >= start_date)
    if end_date is not None:
        query = query.filter(GerritChange.updated_at <= end_date)
    if owner:
        query = query.filter(GerritChange.owner.in_(owner))
    if project:
        query = query.filter(GerritChange.project.in_(project))
    if status:
        query = query.filter(GerritChange.status.in_(status))

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

        if status:
            if raw.get("status") not in status:
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

def create_team(name, members, projects=None):
    db = SessionLocal()

    try:
        existing = (
            db.query(Team)
            .filter(Team.name == name)
            .first()
        )

        if existing:
            return None

        members = list(dict.fromkeys(members))
        projects = list(dict.fromkeys(projects or []))

        team = Team(name=name)

        team.members = [
            TeamMember(username=username)
            for username in members
        ]

        if projects:
            project_rows = (
                db.query(Project)
                .filter(Project.name.in_(projects))
                .all()
            )

            found_names = {p.name for p in project_rows}
            missing = set(projects) - found_names
            if missing:
                raise ValueError(f"Unknown projects: {sorted(missing)}")

            team.projects = [
                TeamDefaultProject(project_id=project_row.id)
                for project_row in project_rows
            ]

        db.add(team)
        db.commit()

        team = (
            db.query(Team)
            .options(selectinload(Team.members))
            .options(selectinload(Team.projects).selectinload(TeamDefaultProject.project))
            .filter(Team.id == team.id)
            .first()
        )

        return team

    finally:
        db.close()

def get_teams():
    db = SessionLocal()

    try:
        return (
            db.query(Team)
            .options(
                selectinload(Team.members),
                selectinload(Team.projects).selectinload(TeamDefaultProject.project),
            )
            .order_by(Team.name)
            .all()
        )
    finally:
        db.close()

def get_devs():
    db = SessionLocal()
    try:
        return (
            row.username
            for row in db.query(Dev)
            .order_by(Dev.username)
            .all()
        )
    finally:
        db.close()

def update_devs(developers: list[str]):
    db = SessionLocal()
    try:
        db.query(Dev).delete()

        for username in developers:
            db.add(Dev(username=username))

        db.commit()
    finally:
            db.close()

def get_projects():
    db = SessionLocal()
    try:
        return (
            row.name
            for row in db.query(Project)
            .order_by(Project.name)
            .all()
        )
    finally:
        db.close()

def update_projects(projects: list[str]):
    db = SessionLocal()
    try:
        db.query(Project).delete()

        for name in projects:
            db.add(Project(name=name))

        db.commit()
    finally:
            db.close()

def get_team(team_id):
    db = SessionLocal()
    try:
        return (
            db.query(Team)
            .options(
                selectinload(Team.members),
                selectinload(Team.projects).selectinload(TeamDefaultProject.project),
            )
            .filter(Team.id == team_id)
            .first()
        )
    finally:
        db.close()


def update_team(team_id, name=None, members=None, projects=None):
    db = SessionLocal()

    try:
        team = (
            db.query(Team)
            .filter(Team.id == team_id)
            .first()
        )

        if not team:
            return None

        if name is not None:
            existing = (
                db.query(Team)
                .filter(
                    Team.name == name,
                    Team.id != team_id,
                )
                .first()
            )

            if existing:
                return "duplicate"

            team.name = name

        if members is not None:
            new_members = set(members)

            existing_members = {
                member.username: member
                for member in team.members
            }

            existing_names = set(existing_members.keys())

            for username in new_members - existing_names:
                team.members.append(
                    TeamMember(username=username)
                )

            for username in existing_names - new_members:
                db.delete(existing_members[username])

        if projects is not None:
            new_project_names = set(projects)

            existing_links = {
                link.project.name: link
                for link in team.projects
            }

            existing_project_names = set(existing_links.keys())

            names_to_add = new_project_names - existing_project_names
            if names_to_add:
                project_rows = (
                    db.query(Project)
                    .filter(Project.name.in_(names_to_add))
                    .all()
                )

                found_names = {p.name for p in project_rows}
                missing = names_to_add - found_names
                if missing:
                    # decide policy: raise, skip, or auto-create
                    raise ValueError(f"Unknown projects: {missing}")

                for project_row in project_rows:
                    team.projects.append(
                        TeamDefaultProject(project_id=project_row.id)
                    )

            for name_to_remove in existing_project_names - new_project_names:
                db.delete(existing_links[name_to_remove])

        db.commit()

        team = (
            db.query(Team)
            .options(
                selectinload(Team.members),
                selectinload(Team.projects).selectinload(
                    TeamDefaultProject.project
                ),
            )
            .filter(Team.id == team_id)
            .first()
        )

        return team

    finally:
        db.close()
def delete_team(team_id):
    db = SessionLocal()

    try:
        team = (
            db.query(Team)
            .filter(Team.id == team_id)
            .first()
        )

        if not team:
            return False

        db.delete(team)
        db.commit()

        return True

    finally:
        db.close()