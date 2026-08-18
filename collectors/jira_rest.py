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

def fetch_issues(
    project=None,
    boards=None,
    issue_key=None,
    start_date=None,
    end_date=None,
    max_results=100,
):
    # Specific issue
    if issue_key:
        jql = f"key = {issue_key}"

        data = jira_get(
            "/rest/api/2/search",
            {
                "jql": jql,
                "maxResults": 1,
                "fields": ISSUE_FIELDS,
            },
        )

        return data.get("issues", [])

    # Board-filtered issues
    if boards:
        issues = {}

        for board_id in boards:
            start_at = 0

            while True:
                data = jira_get(
                    f"/rest/agile/1.0/board/{board_id}/issue",
                    {
                        "startAt": start_at,
                        "maxResults": max_results,
                        "fields": ISSUE_FIELDS,
                    },
                )

                batch = data.get("issues", [])

                for issue in batch:
                    issues[issue["id"]] = issue

                if len(batch) < max_results:
                    break

                start_at += len(batch)

        return list(issues.values())

    # Project issues
    jql = []

    if project:
        jql.append(f"project = {project}")

    if start_date:
        jql.append(f'created >= "{start_date}"')

    if end_date:
        jql.append(f'created <= "{end_date}"')

    jql_string = " AND ".join(jql)

    issues = []
    start_at = 0

    while True:
        data = jira_get(
            "/rest/api/2/search",
            {
                "jql": jql_string,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": ISSUE_FIELDS,
            },
        )

        batch = data.get("issues", [])
        issues.extend(batch)

        if len(batch) < max_results:
            break

        start_at += len(batch)

    return issues