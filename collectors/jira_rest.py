import requests
from config import JIRA_URL, JIRA_TOKEN

headers = {
    "Authorization": f"Bearer {JIRA_TOKEN}",
    "Accept": "application/json",
}

ISSUE_FIELDS = (
    "summary,status,assignee,priority,issuetype,"
    "created,updated,resolutiondate,reporter,"
    "labels,components,fixVersions"
)


def jira_get(endpoint, params=None):
    r = requests.get(
        f"{JIRA_URL}{endpoint}",
        headers=headers,
        params=params,
        verify=False,
    )

    print("Status:", r.status_code)

    if not r.ok:
        print(r.text)
        r.raise_for_status()

    return r.json()

def fetch_project_issues(
    project,
    start_date=None,
    end_date=None,
    max_results=50,
):
    jql = f"project = {project}"

    if start_date:
        jql += f' AND updated >= "{start_date}"'

    if end_date:
        jql += f' AND updated <= "{end_date}"'

    jql += " ORDER BY updated DESC"

    return jira_get(
        "/rest/api/2/search",
        {
            "jql": jql,
            "maxResults": max_results,
            "fields": ISSUE_FIELDS,
        },
    )

def fetch_board_issues(
    boards,
    max_results=50,
):
    issues = {}

    for board_id in boards:
        data = jira_get(
            f"/rest/agile/1.0/board/{board_id}/issue",
            {
                "maxResults": max_results,
            },
        )

        for issue in data.get("issues", []):
            issues[issue["id"]] = issue

    return {
        "issues": list(issues.values()),
        "total": len(issues),
    }

def fetch_issues(
    project=None,
    boards=None,
    issue_key=None,
    start_date=None,
    end_date=None,
    max_results=50,
):
    # Specific issue
    if issue_key:
        jql = f"key = {issue_key}"

        return jira_get(
            "/rest/api/2/search",
            {
                "jql": jql,
                "maxResults": max_results,
                "fields": ISSUE_FIELDS,
            },
        )

    # Board-filtered issues
    if boards:
        issues = {}

        for board_id in boards:
            data = jira_get(
                f"/rest/agile/1.0/board/{board_id}/issue",
                {
                    "maxResults": max_results,
                },
            )

            for issue in data.get("issues", []):
                issues[issue["id"]] = issue

        return {
            "total": len(issues),
            "issues": list(issues.values()),
        }

    # Project issues
    jql = []

    if project:
        jql.append(f"project = {project}")

    if start_date:
        jql.append(f'created >= "{start_date}"')

    if end_date:
        jql.append(f'created <= "{end_date}"')

    jql_string = " AND ".join(jql)

    return jira_get(
        "/rest/api/2/search",
        {
            "jql": jql_string,
            "maxResults": max_results,
            "fields": ISSUE_FIELDS,
        },
    )
def count_issues(jql="project = DEVOPS"):
    data = jira_get(
        "/rest/api/2/search",
        {
            "jql": jql,
            "maxResults": 0,
        },
    )

    return data["total"]

def fetch_all_issues(jql="project = DEVOPS"):
    issues = []
    start_at = 0
    max_results = 100

    while True:
        data = jira_get(
            "/rest/api/2/search",
            {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ISSUE_FIELDS,
            },
        )

        batch = data["issues"]
        issues.extend(batch)

        if len(issues) >= data["total"] or not batch:
            break

        start_at += len(batch)

    return issues

def fetch_projects():
    return jira_get("/rest/api/2/project")

def fetch_boards(project=None):
    params = {}

    if project:
        params["projectKeyOrId"] = project

    data = jira_get(
        "/rest/agile/1.0/board",
        params=params,
    )

    return data.get("values", [])