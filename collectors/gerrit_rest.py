import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Iterable

import requests
import urllib3

from config import (
    GERRIT_HOST,
    GERRIT_HTTP_PASSWORD,
    GERRIT_HTTP_USER,
    GERRIT_REST_URL,
    GERRIT_USER,
)

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def _gerrit_base_url() -> str:
    if GERRIT_REST_URL:
        base = GERRIT_REST_URL.rstrip("/")
        if not base.endswith("/a"):
            return f"{base}/a"
        return base

    return f"https://{GERRIT_HOST}/a"


def _gerrit_auth() -> tuple[str, str]:
    username = GERRIT_HTTP_USER or GERRIT_USER
    return username, GERRIT_HTTP_PASSWORD


def _request_json(method: str, path: str, params=None, timeout: int = 30):
    url = f"{_gerrit_base_url()}{path}"
    response = requests.request(
        method,
        url,
        params=params,
        auth=_gerrit_auth(),
        verify=False,
        timeout=timeout,
    )

    if response.status_code == 404:
        return {}

    response.raise_for_status()

    text = response.text.strip()
    if not text:
        return {}

    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]

    return json.loads(text)


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]

    return [value]


def _quote_query_value(value):
    text = str(value).strip()
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or '"' in text or ':' in text:
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


def _append_query_group(parts, key, value):
    values = [str(v).strip() for v in _as_list(value) if str(v).strip()]
    if not values:
        return

    if len(values) == 1:
        parts.append(f"{key}:{_quote_query_value(values[0])}")
        return

    group = " OR ".join(f"{key}:{_quote_query_value(v)}" for v in values)
    parts.append(f"({group})")


def _date_value(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    return str(value)


def _filter_from_values(value, allowed):
    allowed = set(str(v) for v in _as_list(allowed))
    values = [str(v) for v in _as_list(value)]
    return any(v in allowed for v in values)


def _matches_any(value, accepted):
    accepted_values = set(str(v) for v in _as_list(accepted))
    return any(str(v) in accepted_values for v in _as_list(value))


def _normalize_change(change):
    owner = change.get("owner") or {}
    if isinstance(owner, dict):
        owner_username = owner.get("username") or owner.get("name")
    else:
        owner_username = owner

    if isinstance(change.get("reviewers"), dict):
        reviewers = []
        for values in change["reviewers"].values():
            if isinstance(values, list):
                reviewers.extend(values)
    else:
        reviewers = change.get("allReviewers", [])

    normalized = dict(change)
    normalized["owner"] = owner if isinstance(owner, dict) else {"username": owner_username}
    normalized["allReviewers"] = reviewers
    normalized["createdOn"] = change.get("createdOn") or change.get("created")
    normalized["lastUpdated"] = change.get("lastUpdated") or change.get("updated")
    normalized["reviewer_updates"] = change.get("reviewer_updates", [])
    normalized["raw_json"] = normalized

    if "number" not in normalized and "_number" in normalized:
        normalized["number"] = normalized["_number"]

    return normalized


def fetch_change_detail(change_number: int) -> dict:
    detail = _request_json(
        "GET",
        f"/changes/{change_number}/detail",
    )
    if not isinstance(detail, dict):
        return {}

    return detail


def enrich_reviewer_updates(changes, max_workers=10):
    """
    Fetch reviewer_updates for every change in parallel.
    """

    def load(change):

        reviewers = {
            r.get("username")
            for r in change.get("allReviewers", [])
            if isinstance(r, dict)
        }

        if "jenkins" in reviewers and len(reviewers) == 1:
            change["reviewer_updates"] = []
            return change

        detail = fetch_change_detail(change["number"])
        change["reviewer_updates"] = detail.get("reviewer_updates", [])
        return change

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(load, changes))


def fetch_changes(
    start_date=None,
    end_date=None,
    owner=None,
    project=None,
    topic=None,
    reviewer=None,
    commenter=None,
    status=None,
    issue=None,
    options=None,
):
    """
    Fetch Gerrit changes using the REST API while keeping the same argument shape
    as the SSH-based helper used elsewhere in the project.
    """

    def build_query_parts(include_status_filter=True):
        query_parts = []

        start_value = _date_value(start_date)
        end_value = _date_value(end_date)

        if start_value:
            query_parts.append(f"after:{start_value}")
        if end_value:
            query_parts.append(f"before:{end_value}")

        for key, value in (
            ("owner", owner),
            ("project", project),
            ("topic", topic),
            ("reviewer", reviewer),
            ("commentby", commenter),
        ):
            if key != "status":
                _append_query_group(query_parts, key, value)

        if include_status_filter:
            _append_query_group(query_parts, "status", status)

        if issue:
            for item in _as_list(issue):
                query_parts.append(f"message:{_quote_query_value(item)}")

        if not query_parts:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=365)
            query_parts.append(f"after:{start_dt.strftime('%Y-%m-%d')}")
            query_parts.append(f"before:{end_dt.strftime('%Y-%m-%d')}")

        return query_parts

    params = {
        "q": " ".join(build_query_parts()),
        "n": 500,
        "o": "CURRENT_REVISION",
    }

    response = None
    try:
        response = _request_json("GET", "/changes", params=params)
    except requests.HTTPError as exc:
        if status is None:
            raise

        params["q"] = " ".join(build_query_parts(include_status_filter=False))
        response = _request_json("GET", "/changes", params=params)

    if isinstance(response, list):
        changes = response
    elif isinstance(response, dict):
        changes = response.get("changes") or response.get("results") or []
    else:
        changes = []

    normalized = [_normalize_change(change) for change in changes]

    def matches_owner(change_item):
        owner_name = (change_item.get("owner") or {}).get("username")
        if owner is None:
            return True
        return owner_name in {str(v) for v in _as_list(owner)}

    def matches_reviewer(change_item):
        if reviewer is None:
            return True

        reviewer_names = {str(v) for v in _as_list(reviewer)}
        reviewers = change_item.get("allReviewers", [])
        reviewer_usernames = {
            item.get("username")
            for item in reviewers
            if isinstance(item, dict) and item.get("username")
        }
        return bool(reviewer_usernames & reviewer_names)

    def matches_commenter(change_item):
        if commenter is None:
            return True

        commenter_names = {str(v) for v in _as_list(commenter)}
        comments = change_item.get("messages", [])
        for comment in comments:
            author = (comment.get("author") or {}).get("username")
            if author in commenter_names:
                return True
        return False

    filtered = []
    accepted_statuses = {str(v).upper() for v in _as_list(status)} if status is not None else None

    for change_item in normalized:
        if not matches_owner(change_item):
            continue
        if not matches_reviewer(change_item):
            continue
        if not matches_commenter(change_item):
            continue

        if project is not None and not _matches_any(change_item.get("project"), project):
            continue
        if topic is not None and not _matches_any(change_item.get("topic") or "untagged", topic):
            continue
        if accepted_statuses is not None and str(change_item.get("status", "")).upper() not in accepted_statuses:
            continue
        if issue is not None:
            subject = (change_item.get("subject") or "")
            if not any(str(item).lower() in subject.lower() for item in _as_list(issue)):
                continue

        filtered.append(change_item)

    if filtered:
        with ThreadPoolExecutor(max_workers=10) as executor:
            details = list(executor.map(lambda change: fetch_change_detail(change["number"]), filtered))

        for change, detail in zip(filtered, details):
            change["reviewer_updates"] = detail.get("reviewer_updates", [])
            change["allReviewers"] = detail.get("allReviewers", change.get("allReviewers", []))

    return filtered


def ls_projects():
    """Return a list of Gerrit project names via the REST API."""
    payload = _request_json("GET", "/projects")
    if isinstance(payload, dict):
        return sorted(payload.keys())
    if isinstance(payload, list):
        return sorted(str(item) for item in payload)
    return []


def ls_groups():
    """Return the list of Gerrit groups using the REST API."""
    payload = _request_json("GET", "/groups")
    if isinstance(payload, dict):
        return sorted(payload.keys())
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return []


def ls_members(group, recursive=False):
    """Return members for a Gerrit group."""
    path = f"/groups/{group}/members"
    payload = _request_json("GET", path)

    if isinstance(payload, list):
        members = []
        for member in payload:
            if isinstance(member, dict):
                username = member.get("username") or member.get("name")
                if username:
                    members.append(username)
            else:
                members.append(str(member))
        return members

    if isinstance(payload, dict):
        members = payload.get("members") or payload.get("users") or []
        return [
            (m.get("username") or m.get("name") or str(m))
            for m in members
        ]

    return []


def all_members():
    """Return unique members from all Gerrit groups containing 'Developers'."""
    groups = ls_groups()
    developer_groups = [group for group in groups if "developers" in str(group).lower()]
    members = set()

    for group in developer_groups:
        members.update(ls_members(group))

    return sorted(members)


def fetch_changes_from_json(start_date=None, end_date=None, owner=None, project=None, topic=None, reviewer=None, options=None):
    """Compatibility wrapper retained for local mock usage."""
    import os

    json_path = os.path.join(os.getcwd(), "data", "mock_data.json")
    if not os.path.exists(json_path):
        return []

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Expected mock_data.json to contain a JSON array")

    return data


def get_members_for_group(group, recursive=False):
    return ls_members(group, recursive=recursive)
