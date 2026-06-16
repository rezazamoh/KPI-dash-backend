from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from database.crud import (
    get_all_developers,
    get_all_projects,
    get_latest_snapshot,
    get_all_gerrit_changes,
    get_gerrit_changes_by_date,
)
from kpis.gerrit_kpis import (
    developer_performance_by_repo,
    developer_performance_by_developer_repo,
    developer_performance_by_topic,
    developer_performance_by_developer_topic,
)

router = APIRouter()


def _parse_date(value: str):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {value}. Use YYYY-MM-DD or ISO format."
        )


@router.get("/developers")
def developers(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None)
):
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together."
        )

    parsed_start = None
    parsed_end = None
    if start_date and end_date:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date)

    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date
        },
        "developers": get_all_developers(
            start_date=parsed_start,
            end_date=parsed_end
        )
    }


@router.get("/developers/{username}")
def developer(username):
    snapshot = get_latest_snapshot(username)

    if not snapshot:
        return {
            "error": "developer not found"
        }

    return {
        "username": username,
        "snapshot_time": snapshot.snapshot_time,
        "metrics": snapshot.metrics_json
    }


@router.get("/developers/performance/{username}")
def developer_performance_by_username(
    username: str,
    repo: str | None = Query(None),
    topic: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None)
):
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together."
        )

    if start_date and end_date:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date)
        changes = get_gerrit_changes_by_date(
            parsed_start,
            parsed_end,
            username=username
        )
    else:
        changes = get_all_gerrit_changes()

    repo_performance = developer_performance_by_developer_repo(
        changes,
        username=username,
        repo=repo,
        topic=topic
    )

    topic_performance = developer_performance_by_developer_topic(
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
            "end_date": end_date
        },
        "repo_performance": repo_performance,
        "topic_performance": topic_performance
    }


@router.get("/projects")
def projects(
    username: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None)
):
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together."
        )

    parsed_start = None
    parsed_end = None
    if start_date and end_date:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date)

    return {
        "filters": {
            "username": username,
            "start_date": start_date,
            "end_date": end_date
        },
        "projects": get_all_projects(
            username=username,
            start_date=parsed_start,
            end_date=parsed_end
        )
    }


@router.get("/projects/performance/{project:path}")
def project_performance_for(
    project: str,
    username: str | None = Query(None),
    topic: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None)
):
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together."
        )

    if start_date and end_date:
        parsed_start = _parse_date(start_date)
        parsed_end = _parse_date(end_date)
        changes = get_gerrit_changes_by_date(
            parsed_start,
            parsed_end,
            username=username
        )
    else:
        changes = get_all_gerrit_changes()

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