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
    projects: list[str] = []


class TeamUpdate(BaseModel):
    name: str | None = None
    members: list[str] | None = None
    projects: list[str] | None = None

def parse_periods(periods: list[str] | None):
    if not periods:
        return [(None, None)]

    result = []

    for period in periods:
        parts = period.split(",")

        if len(parts) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period '{period}'. Expected start,end.",
            )

        start, end = parts

        result.append((
            start.strip() or None,
            end.strip() or None,
        ))

    return result

def serialize_team(team):
    return {
        "id": team.id,
        "name": team.name,
        "members": [
            member.username
            for member in team.members
        ],
        "projects": [
            link.project.name
            for link in team.projects
            if link.project is not None
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
    status: list[str] | None = Query(None),
    periods: list[str] | None = Query(None),
    group_by_repo: bool = Query(False),
    group_by_topic: bool = Query(False),
    live: bool = Query(True),
):
    results = []

    for start_date, end_date in parse_periods(periods):

        owner_changes = load_changes(
            username=username,
            project=repo,
            topic=topic,
            status=status,         
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        reviewer_changes = load_changes(
            reviewer=username,
            project=repo,
            topic=topic,
            status=status,
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
            status=status,
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        metrics = {
            "username": username,
            "snapshot_time": datetime.now(),
            "live": live,
            "filters": {
                "repo": repo,
                "topic": topic,
            },
            "overall_performance": developer_snapshot_metrics(
                username,
                dev_changes=owner_changes,
                reviewer_changes=reviewer_changes,
                commenter_changes=commenter_changes,
            ),
        }

        if group_by_repo:
            metrics["grouped_by_repo"] = developer_performance_grouped(
                username=username,
                dev_changes=owner_changes,
                reviewer_changes=reviewer_changes,
                commenter_changes=commenter_changes,
                group_by="project",
            )

        if group_by_topic:
            metrics["grouped_by_topic"] = developer_performance_grouped(
                username=username,
                dev_changes=owner_changes,
                reviewer_changes=reviewer_changes,
                commenter_changes=commenter_changes,
                group_by="topic",
            )

        results.append({
            "start": start_date,
            "end": end_date,
            "metrics": metrics,
        })

    return results

@router.get("/developers/{username}/topics")
def gerrit_developer_topics(
    username: str,
    repo: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):
    changes = load_changes(
        username=username,
        project=repo,
        status=status,
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
    status: list[str] | None = Query(None),
    periods: list[str] | None = Query(None),
    live: bool = Query(True),
):
    results = []

    for start_date, end_date in parse_periods(periods):

        owner_changes = load_changes(
            username=username,
            project=project,
            topic=topic,
            status=status,           
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        reviewer_changes = load_changes(
            reviewer=username,
            project=project,
            topic=topic,
            status=status,         
            start_date=start_date,
            end_date=end_date,
            live=live,
        )
        """ 
        if live:
            reviewer_changes = enrich_reviewer_updates(reviewer_changes)
        """
            
        commenter_changes = load_changes(
            commenter=username,
            project=project,
            topic=topic,
            status=status,          
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        developers = sorted({
            (c.get("author") or {}).get("username")
            for c in owner_changes
            if (c.get("author") or {}).get("username")
        })

        topics = sorted({
            c.get("topic")
            for c in owner_changes
            if c.get("topic")
        })

        metrics = {
            "filters": {
                "project": project,
                "developers": username,
                "topics": topic,
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

        results.append({
            "start": start_date,
            "end": end_date,
            "metrics": metrics,
        })

    return results

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
        projects=data.projects,
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
        projects=data.projects,
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
    username: list[str] | None = Query(None),
    project: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    periods: list[str] | None = Query(None),
    live: bool = Query(True),
):
    team = get_team(team_id)

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found.",
        )

    if username:
        members = username
    else:
        members = [
            member.username
            for member in team.members
        ]

    results = []

    for start_date, end_date in parse_periods(periods):

        if not members:
            metrics = {
                "team": serialize_team(team),
                "filters": {
                    "repo": project,
                    "topic": topic,
                    "live": live,
                },
                "overall_performance": {
                    "change_count": 0,
                },
                "developers": [],
                "projects": [],
                "topics": [],
            }

            results.append({
                "start": start_date,
                "end": end_date,
                "metrics": metrics,
            })

            continue

        owner_changes = load_changes(
            username=members,
            project=project,
            topic=topic,
            status=status,      
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        reviewer_changes = load_changes(
            reviewer=members,
            project=project,
            topic=topic,
            status=status,         
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        """        
        if live:
        reviewer_changes = enrich_reviewer_updates(reviewer_changes)
        """
        commenter_changes = load_changes(
            commenter=members,
            project=project,
            topic=topic,
            status=status,        
            start_date=start_date,
            end_date=end_date,
            live=live,
        )

        developers = sorted({
            (change.get("author") or {}).get("username")
            for change in owner_changes
            if (change.get("author") or {}).get("username")
        })

        projects = sorted({
            change.get("project")
            for change in owner_changes
            if change.get("project")
        })

        topics = sorted({
            change.get("topic")
            for change in owner_changes
            if change.get("topic")
        })

        metrics = {
            "team": serialize_team(team),
            "filters": {
                "project": project,
                "topics": topic,
                "live": live,
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

        results.append({
            "start": start_date,
            "end": end_date,
            "metrics": metrics,
        })

    return results