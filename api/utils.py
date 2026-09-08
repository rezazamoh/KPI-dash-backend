from datetime import datetime

from fastapi import HTTPException

from collectors.jira_rest import fetch_issues , fetch_boards , fetch_projects
from collectors.gerrit_ssh import fetch_changes
from database.crud import get_gerrit_changes, get_jira_issues, get_jira_projects


def _parse_date(value: str):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {value}. Use YYYY-MM-DD or ISO format."
        )


def parse_date_range(start_date: str | None, end_date: str | None):
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date are required together."
        )

    if not start_date:
        return None, None

    return _parse_date(start_date), _parse_date(end_date)


def load_changes(
    start_date=None,
    end_date=None,
    live=False,
    username=None,      # str | list[str]
    reviewer=None,      # str | list[str]
    commenter=None,     # str | list[str]
    project=None,       # str | list[str]
    topic=None,         # str | list[str]
    status=None,        # str | list[str]
    issue=None,         # str | list[str]
    options=None,
):
    parsed_start, parsed_end = parse_date_range(start_date, end_date)

    if live:
        return fetch_changes(
            start_date=parsed_start,
            end_date=parsed_end,
            author=username,
            reviewer=reviewer,
            commenter=commenter,
            project=project,
            topic=topic,
            status=status,
            issue=issue,
            options=options,
        )

    return get_gerrit_changes(
        start_date=parsed_start,
        end_date=parsed_end,
        author=username,
        reviewer=reviewer,
        commenter=commenter,
        project=project,
        topic=topic,
        status=status,
    )

def load_jira_projects_list(live=False):
    if live:
        return fetch_projects()
    return get_jira_projects()

def load_boards_list(project=None, live=False):
    if live:
        return fetch_boards(project)
    #return get_boards_projects

def load_issues(
    project=None,
    boards=None,
    issue_key=None,
    start_date=None,
    end_date=None,
    live=False,
):
    if live:
        return fetch_issues(
            project=project,
            boards=boards,
            issue_key=issue_key,
            start_date=start_date,
            end_date=end_date,
        )

    return get_jira_issues(
        project=project,
        boards=boards,
        issue_key=issue_key,
        start_date=start_date,
        end_date=end_date,
    )
