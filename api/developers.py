from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kpis.gerrit_kpis import (
    developer_performance_grouped,
    developer_snapshot_metrics,
    project_developer_metrics,
)
from api.utils import load_changes
from collectors.gerrit_ssh import ls_projects

router = APIRouter()

@router.get("/developers")
def developers(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(True)
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
    live: bool = Query(True),
):

    owner_changes = load_changes(
        username=username,
        project=repo,
        topic=topic,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[
            "--all-reviewers",
            "--patch-sets",
            "--current-patch-set",
        ]
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

@router.get("/developers/{username}/projects")
def developer_projects(
    username: str,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(False),
):
    changes = load_changes(
        username=username,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[],
    )

    projects = sorted({
        c.get("project")
        for c in changes
        if c.get("project")
    })

    return {
        "username": username,
        "projects": projects,
    }

@router.get("/developers/{username}/topics")
def developer_topics(
    username: str,
    repo: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(False),
):
    changes = load_changes(
        username=username,
        project=repo,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[],
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
def projects(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(True)
):
    if live and not start_date and not end_date:
        projects = sorted(ls_projects())
    else:
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

@router.get("/projects/{project:path}/developers")
def project_developers(
    project: str,
    topic: list[str] | None = Query(None),
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
        options=[],
    )

    developers = sorted({
        (c.get("owner") or {}).get("username")
        for c in changes
        if (c.get("owner") or {}).get("username")
    })

    return {
        "project": project,
        "topics": topic,
        "developers": developers,
    }

@router.get("/projects/{project:path}/topics")
def project_topics(
    project: str,
    username: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(False),
):
    changes = load_changes(
        username=username,
        project=project,
        start_date=start_date,
        end_date=end_date,
        live=live,
        options=[],
    )

    topics = sorted({
        c.get("topic")
        for c in changes
        if c.get("topic")
    })

    return {
        "project": project,
        "developers": username,
        "topics": topics,
    }