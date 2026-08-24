from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kpis.gerrit_kpis import (
    developer_performance_grouped,
    developer_snapshot_metrics,
    project_developer_metrics,
)
from api.utils import load_changes
from collectors.gerrit_ssh import ls_projects , all_members
from collectors.gerrit_rest import enrich_reviewer_updates
from pydantic import BaseModel
from database.crud import (
    create_team,
    get_teams,
    get_team,
    update_team,
    delete_team,
    get_devs,
    update_devs,
    get_projects,
    update_projects,
)

class TeamCreate(BaseModel):
    name: str
    members: list[str]


class TeamUpdate(BaseModel):
    name: str | None = None
    members: list[str] | None = None

def serialize_team(team):
    return {
        "id": team.id,
        "name": team.name,
        "members": [
            member.username
            for member in team.members
        ],
    }

router = APIRouter(prefix="/api/gerrit", tags=["Gerrit"])

@router.get("/developers")
def gerrit_developers(
    live: bool | None = Query(True)
):
    if live:
        devs = all_members()
        update_devs(devs)
        return {"developers": devs}
    
    return {"developers": get_devs()}

@router.get("/developers/{username}")
def gerrit_developer(
    username: str,
    repo: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    group_by_repo: bool = Query(False),
    group_by_topic: bool = Query(False),
    live: bool = Query(True),
):

    owner_changes = load_changes(
        username=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    reviewer_changes = load_changes(
        reviewer=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )
    if live:
        reviewer_changes = enrich_reviewer_updates(reviewer_changes)

    commenter_changes = load_changes(
        commenter=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    response = {
        "username": username,
        "snapshot_time": datetime.now(),
        "live": live,
        "filters": {
            "repo": repo,
            "topic": topic,
            "start_date": start_date,
            "end_date": end_date,
        },
        "overall_performance": developer_snapshot_metrics(
            username,
            dev_changes=owner_changes,
            reviewer_changes=reviewer_changes,
            commenter_changes=commenter_changes,
        ),
    }

    if group_by_repo:
        response["grouped_by_repo"] = developer_performance_grouped(
            username=username,
            dev_changes=owner_changes,
            reviewer_changes=reviewer_changes,
            commenter_changes=commenter_changes,
            group_by="project",
        )

    if group_by_topic:
        response["grouped_by_topic"] = developer_performance_grouped(
            username=username,
            dev_changes=owner_changes,
            reviewer_changes=reviewer_changes,
            commenter_changes=commenter_changes,
            group_by="topic",
        )

    return response

@router.get("/developers/{username}/topics")
def gerrit_developer_topics(
    username: str,
    repo: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):
    changes = load_changes(
        username=username,
        project=repo,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[]
    )

    topics = sorted({
        c.get("topic")
        for c in changes
        if c.get("topic")
    })

    return {
        "username": username,
        "projects": repo,
        "topics": topics,
    }

@router.get("/projects")
def gerrit_projects(
    live: bool | None = Query(True)
):
    if live:
        projects = ls_projects()
        update_projects(projects)
        return {"projects": projects}
    
    return {"projects": get_projects()}

@router.get("/projects/{project:path}")
def gerrit_project(
    project: str,
    username: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):

    owner_changes = load_changes(
        username=username,
        project=project,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    reviewer_changes = load_changes(
        reviewer=username,
        project=project,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    commenter_changes = load_changes(
        commenter=username,
        project=project,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    developers = sorted({
        (c.get("owner") or {}).get("username")
        for c in owner_changes
        if (c.get("owner") or {}).get("username")
    })

    topics = sorted({
        c.get("topic")
        for c in owner_changes
        if c.get("topic")
    })

    return {
        "filters": {
            "project": project,
            "developers": username,
            "topics": topic,
            "start_date": start_date,
            "end_date": end_date,
            "live": live,
        },
        "developers": developers,
        "topics": topics,
        "developer_metrics": project_developer_metrics(
            owner_changes,
            reviewer_changes,
            commenter_changes,
        ),
    }

@router.get("/teams")
def list_teams():
    teams = get_teams()

    return [
        serialize_team(team)
        for team in teams
    ]

@router.post("/teams")
def create_team_api(data: TeamCreate):
    team = create_team(
        name=data.name,
        members=data.members,
    )

    if team is None:
        raise HTTPException(
            status_code=409,
            detail="A team with this name already exists.",
        )

    return serialize_team(team)

@router.get("/teams/{team_id}")
def get_team_api(team_id: int):
    team = get_team(team_id)

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found.",
        )

    return serialize_team(team)


@router.put("/teams/{team_id}")
def update_team_api(
    team_id: int,
    data: TeamUpdate,
):
    team = update_team(
        team_id=team_id,
        name=data.name,
        members=data.members,
    )

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found.",
        )

    if team == "duplicate":
        raise HTTPException(
            status_code=409,
            detail="A team with this name already exists.",
        )

    return serialize_team(team)


@router.delete("/teams/{team_id}")
def delete_team_api(team_id: int):
    deleted = delete_team(team_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Team not found.",
        )

    return {
        "message": "Team deleted successfully.",
        "team_id": team_id,
    }

@router.get("/teams/{team_id}/performance")
def gerrit_team_performance(
    team_id: int,
    repo: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):
    team = get_team(team_id)

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found.",
        )

    members = [
        member.username
        for member in team.members
    ]

    if not members:
        return {
            "team": serialize_team(team),
            "filters": {
                "repo": repo,
                "topic": topic,
                "start_date": start_date,
                "end_date": end_date,
            },
            "overall_performance": {
                "change_count": 0,
            },
            "developers": [],
            "projects": [],
        }

    owner_changes = load_changes(
        username=members,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live
    )

    reviewer_changes = load_changes(
        reviewer=members,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live
    )

    commenter_changes = load_changes(
        commenter=members,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live
    )

    developers = sorted({
        (change.get("owner") or {}).get("username")
        for change in owner_changes
        if (change.get("owner") or {}).get("username")
    })

    projects = sorted({
        change.get("project")
        for change in owner_changes
        if change.get("project")
    })

    topics = sorted({
        c.get("topic")
        for c in owner_changes
        if c.get("topic")
    })

    return {
        "team": serialize_team(team),
        "filters": {
            "project": repo,
            "topics": topic,
            "start_date": start_date,
            "end_date": end_date,
        },
        "developers": developers,
        "projects": projects,
        "topics": topics,
        "developer_metrics": project_developer_metrics(
            owner_changes,
            reviewer_changes,
            commenter_changes,
        ),
    }