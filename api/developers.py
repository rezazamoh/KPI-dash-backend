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
    commenter_changes = load_changes(
        commenter=username,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=["--all-reviewers", "--comments", "--current-patch-set"],
    )
    print(f'Owner_changes: {len(owner_changes)}')
    print(f'================================')
    print(f'reviewer_changes: {len(reviewer_changes)}')
    metrics = developer_snapshot_metrics(username,dev_changes=owner_changes, reviewer_changes=reviewer_changes,commenter_changes=commenter_changes)
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
    live: bool = Query(False),
):

    dev_changes = load_changes(
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

    commenter_changes = load_changes(
        commenter=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    return {

        "filters": {
            "username": username,
            "repo": repo,
            "topic": topic,
            "start_date": start_date,
            "end_date": end_date,
            "live": live,
        },

        "repo_performance": developer_performance_grouped(
            username,
            dev_changes,
            reviewer_changes,
            commenter_changes,
            group_by="project",
        ),

        "topic_performance": developer_performance_grouped(
            username,
            dev_changes,
            reviewer_changes,
            commenter_changes,
            group_by="topic",
        ),
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
    topic: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(False),
):

    changes = load_changes(
        project=project,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    return {
        "filters": {
            "project": project,
            "topic": topic,
            "start_date": start_date,
            "end_date": end_date,
            "live": live,
        },
        "developers": project_developer_metrics(changes),
    }