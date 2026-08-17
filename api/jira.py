from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kpis.jira_kpis import (
    calculate_issue_metrics
)
from api.utils import load_issues, load_issues_list, load_boards , load_projects 

router = APIRouter(prefix="/jira", tags=["Jira"])


# ============================================================
# Projects listings
# ============================================================

@router.get("/projects")
def projects(live: bool = Query(True)):
    projects = load_projects(live=live)

    return {
        "live": live,
        "projects": projects,
    }


@router.get("/projects/{project_key}/boards")
def project_boards(
    project_key: str,
    live: bool = Query(True),
):
    boards = load_boards(
        project=project_key,
        live=live,
    )

    return {
        "project": project_key,
        "live": live,
        "boards": boards,
    }


@router.get("/projects/{project_key}/issues")
def project_issues(
    project_key: str,
    boards: list[int] | None = Query(None),
    live: bool = Query(True),
):
    issues = load_issues_list(
        project=project_key,
        boards=boards,
        live=live,
    )

    return {
        "project": project_key,
        "boards": boards,
        "live": live,
        "issues": issues,
    }
# ============================================================
# Project performance
# ============================================================

@router.get("/projects/{project_key}/performance")
def project_performance(
    project_key: str,
    boards: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):
    issues = load_issues(
        project=project_key,
        boards=boards,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    return {
        "project": project_key,
        "snapshot_time": datetime.now(),
        "live": live,
        "filters": {
            "boards": boards,
            "start_date": start_date,
            "end_date": end_date,
        },
        "performance": calculate_issue_metrics(issues),
    }


# ============================================================
# All Jira issues
# ============================================================

@router.get("/issues")
def issues(
    project: list[str] | None = Query(None),
    boards: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool = Query(True),
):
    issues = load_issues(
        project=project,
        boards=boards,
        start_date=start_date,
        end_date=end_date,
        live=live,
    )

    return {
        "snapshot_time": datetime.now(),
        "live": live,
        "filters": {
            "project": project,
            "boards": boards,
            "start_date": start_date,
            "end_date": end_date,
        },
        "count": len(issues),
        "issues": issues,
    }


# ============================================================
# Individual issue
# ============================================================

@router.get("/issues/{issue_key}")
def issue_performance(
    issue_key: str,
    live: bool = Query(True),
):
    issues = load_issues(
        issue_key=issue_key,
        live=live,
    )

    if not issues:
        raise HTTPException(
            status_code=404,
            detail=f"Issue not found: {issue_key}",
        )

    return {
        "issue": issue_key,
        "snapshot_time": datetime.now(),
        "live": live,
        "performance": calculate_issue_metrics(issues),
    }