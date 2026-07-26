from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kpis.gerrit_kpis import (
    developer_performance_by_repo,
    developer_performance_by_topic,
    developer_snapshot_metrics,
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
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):

    owner_changes = load_changes(
        username=username,
        start_date=start_date,
        end_date=end_date,
        live=live
    )
    reviewer_changes = load_changes(
        reviewer=username,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=["--all-reviewers", "--comments", "--current-patch-set"],
    )
    print(f'Owner_changes: {len(owner_changes)}')
    print(f'================================')
    print(f'reviewer_changes: {len(reviewer_changes)}')
    metrics = developer_snapshot_metrics(owner_changes, username, reviewer_changes=reviewer_changes)
    return {
        "username": username,
        "snapshot_time": datetime.utcnow(),
        "metrics": metrics,
        "live": live
    }

@router.get("/developers/performance/{username}")
def developer_performance_by_username(
    username: str,
    repo: str | None = Query(None),
    topic: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):
    changes = load_changes(
        start_date=start_date,
        end_date=end_date,
        live=live,
        username=username,
        project=repo,
        topic=topic,
    )

    repo_performance = developer_performance_by_repo(
        changes,
        username=username,
        repo=repo,
        topic=topic
    )

    topic_performance = developer_performance_by_topic(
        changes,
        username=username,
        topic=topic,
        repo=repo
    )

    return {
        "filters": {
            "username": username,
            "repo": repo,
            "topic": topic,
            "start_date": start_date,
            "end_date": end_date,
            "live": live
        },
        "repo_performance": repo_performance,
        "topic_performance": topic_performance
    }

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

@router.get("/projects/performance/{project:path}")
def project_performance_for(
    project: str,
    username: str | None = Query(None),
    topic: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):
    changes = load_changes(
        start_date=start_date,
        end_date=end_date,
        live=live,
        username=username,
        project=project,
        topic=topic,
    )

    repo_performance = developer_performance_by_repo(
        changes,
        username=username,
        repo=project,
        topic=topic
    )

    topic_performance = developer_performance_by_topic(
        changes,
        username=username,
        topic=topic,
        repo=project
    )

    return {
        "filters": {
            "project": project,
            "username": username,
            "topic": topic,
            "start_date": start_date,
            "end_date": end_date
        },
        "repo_performance": repo_performance,
        "topic_performance": topic_performance
    }