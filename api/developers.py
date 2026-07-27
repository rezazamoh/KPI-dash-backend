from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kpis.gerrit_kpis import (
    developer_performance_grouped,
    developer_snapshot_metrics,
    project_developer_metrics,
)
from api.utils import load_changes

router = APIRouter()

@router.get("/developers")
def developers(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):
    changes = load_changes(
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[],
    )

    devs = sorted({
            (c.get("owner") or {}).get("username")
            for c in changes
            if (c.get("owner") or {}).get("username")
        })
    
    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "live": live
        },
        "developers": devs
    }

@router.get("/developers/{username}")
def developer(
    username: str,
    repo: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    group_by_repo: bool = Query(False),
    group_by_topic: bool = Query(False),
    live: bool = Query(False),
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
        options=[
            "--all-reviewers",
            "--comments",
            "--current-patch-set",
        ],
    )

    commenter_changes = load_changes(
        commenter=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[
            "--all-reviewers",
            "--comments",
            "--current-patch-set",
        ],
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

@router.get("/projects")
def projects(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):
    
    changes = load_changes(
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[],
    )
    projects = sorted({c.get("project") for c in changes if c.get("project")})
    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "live": live
        },
        "projects": projects
    }

@router.get("/projects/{project:path}")
def project(
    project: str,
    username: list[str] | None = Query(None),
    topic: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(False),
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
        options=[
            "--all-reviewers",
            "--comments",
            "--current-patch-set",
        ],
    )

    commenter_changes = load_changes(
        commenter=username,
        project=project,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[
            "--all-reviewers",
            "--comments",
            "--current-patch-set",
        ],
    )

    return {
        "filters": {
            "project": project,
            "developers": username,
            "topics": topic,
            "start_date": start_date,
            "end_date": end_date,
            "live": live,
        },
        "developers": project_developer_metrics(
            owner_changes,
            reviewer_changes,
            commenter_changes,
        ),
    }