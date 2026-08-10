from collections import defaultdict
from datetime import datetime
from statistics import mean
import re

def projects_with_counts(changes_by_status_per_repo):
    totals = {}

    for repos in changes_by_status_per_repo.values():
        for project, count in repos.items():
            totals[project] = totals.get(project, 0) + count

    return [
        {
            "project": project,
            "changes": count,
        }
        for project, count in sorted(totals.items())
    ]

def _people_stats(counter, change_counts):

    if not counter:
        return {
            "people": [],
            "stats": None,
        }

    people = [
        {
            "username": username,
            "count": count,
        }
        for username, count in sorted(
            counter.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    person_values = list(counter.values())

    stats = {
        "per_person": {
            "min": min(person_values),
            "mean": round(mean(person_values), 2),
            "max": max(person_values),
        }
    }

    if change_counts:
        stats["per_change"] = {
            "min": min(change_counts),
            "mean": round(mean(change_counts), 2),
            "max": max(change_counts),
        }

    return {
        "people": people,
        "stats": stats,
    }
def _normalize_owner(change):
    owner = change.get("owner")

    if isinstance(owner, dict):
        return owner.get("username") or owner.get("name")
    
    return owner

def _changes_by_status_per_repo(changes):
    """
    Group changes by status -> repo, returning a count per repo per status.
    
    Args:
        changes: List of Gerrit change dicts
    
    Returns:
        dict: { status: { repo: count } }
    """
    result = defaultdict(lambda: defaultdict(int))
    for c in changes:
        status = c.get("status", "UNKNOWN")
        repo = c.get("project", "unknown")
        result[status][repo] += 1
    return {
        status: dict(repos)
        for status, repos in result.items()
    }

def _average_patchsets(changes):
    if not changes:
        return 0
    return round(
        mean(len(c.get("patchSets", [])) for c in changes),
        2
    )

def _review_requests_received(dev_changes):
    change_review_counts = []

    reviewers = defaultdict(int)

    for change in dev_changes:
        count = 0
        owner = _normalize_owner(change)

        for reviewer in change.get("allReviewers", []):

            username = reviewer.get("username")

            if not username or username == owner or username == 'jenkins':
                continue

            reviewers[username] += 1
            count += 1

        change_review_counts.append(count)

    return _people_stats(reviewers,change_review_counts)

def _review_requests_sent(reviewer_changes, developer):

    reviewer_changes = reviewer_changes or []
    owners = defaultdict(int)
    for change in reviewer_changes:

        owner = _normalize_owner(change)

        if owner != developer:
            owners[owner] += 1

    return _people_stats(owners,[])

def _comments_received(dev_changes):

    commenters = defaultdict(int)
    change_comment_counts = []

    for change in dev_changes:

        owner = _normalize_owner(change)
        count = 0
        for comment in change.get("comments", []):

            reviewer = comment.get("reviewer")

            if not reviewer:
                continue

            username = reviewer.get("username")

            if not username or username == owner or username == "jenkins":
                continue

            commenters[username] += 1
            count += 1
        change_comment_counts.append(count)

    return _people_stats(commenters,change_comment_counts)

def _comments_sent(commenter_changes, developer):
    commenter_changes = commenter_changes or []
    owners = defaultdict(int)
    for change in commenter_changes:

        owner = _normalize_owner(change)

        if owner == developer:
            continue

        for comment in change.get("comments", []):

            reviewer = comment.get("reviewer")

            if not reviewer:
                continue

            username = reviewer.get("username")

            if username != developer:
                continue

            owners[owner] += 1

    return _people_stats(owners,[])

def _reviewer_added_ts(change, username):
    """
    Return the timestamp when `username` was added as a reviewer.
    """

    earliest = None

    for update in change.get("reviewer_updates", []):
        if update.get("state") != "REVIEWER":
            continue

        reviewer = update.get("reviewer", {})
        if reviewer.get("username") != username:
            continue

        ts = update.get("updated")
        if ts is None:
            continue

        ts = int(
            datetime.strptime(
                ts,
                "%Y-%m-%d %H:%M:%S.%f000",
            ).timestamp()
        )

        if earliest is None or ts < earliest:
            earliest = ts

    return earliest


def reviewer_response_time(changes, username):
    """
    Calculate how long it takes `username` to respond after being added
    as a reviewer.

    A response is the earliest of:
      - a review comment
      - an approval/vote

    Returns min/mean/max response time in hours.
    """

    hours = []

    for change in changes:
        added_ts = _reviewer_added_ts(change, username)
        if added_ts is None:
            continue

        first_activity = None

        # Review comments
        for comment in change.get("comments", []):
            if comment.get("reviewer", {}).get("username") != username:
                continue

            ts = comment.get("timestamp")
            if ts is None or ts < added_ts:
                continue

            if first_activity is None or ts < first_activity:
                first_activity = ts

        # Votes / approvals
        sources = []

        cps = change.get("currentPatchSet")
        if isinstance(cps, dict):
            sources.append(cps)

        sources.extend(
            ps for ps in change.get("patchSets", [])
            if isinstance(ps, dict)
        )

        for source in sources:
            for approval in source.get("approvals", []):
                by = approval.get("by", {})
                if by.get("username") != username:
                    continue

                ts = approval.get("grantedOn")
                if ts is None or ts < added_ts:
                    continue

                if first_activity is None or ts < first_activity:
                    first_activity = ts

        if first_activity is not None:
            hours.append((first_activity - added_ts) / 3600)

    if not hours:
        return None

    return {
        "min_hours": round(min(hours), 2),
        "mean_hours": round(mean(hours), 2),
        "max_hours": round(max(hours), 2),
    }

def _lead_time(changes, debug=False):
    """
    Calculate lead time (change creation -> merge).

    Args:
        changes: Developer's changes.
        debug: If True, include the min/max change URLs for verification.
    """

    lead_times = []

    for change in changes:

        if change.get("status") != "MERGED":
            continue

        created_ts = change.get("createdOn")
        updated_ts = change.get("lastUpdated")

        if not created_ts or not updated_ts:
            continue

        created = datetime.fromtimestamp(created_ts)
        updated = datetime.fromtimestamp(updated_ts)
        hours_lt = (updated - created).total_seconds() / 3600

        lead_times.append(
            {
                "hours": hours_lt,
                "url": change.get("url"),
                "change_number": change.get("number"),
            }
        )

    if not lead_times:
        return None

    lead_times.sort(key=lambda x: x["hours"])

    values = [x["hours"] for x in lead_times]

    if not debug:
        return {
            "min": round(values[0], 2),
            "mean": round(mean(values), 2),
            "max": round(values[-1], 2),
        }

    return {
        "min": {
            "hours": round(lead_times[0]["hours"], 2),
            "url": lead_times[0]["url"],
            "change_number": lead_times[0]["change_number"],
        },
        "mean": round(mean(values), 2),
        "max": {
            "hours": round(lead_times[-1]["hours"], 2),
            "url": lead_times[-1]["url"],
            "change_number": lead_times[-1]["change_number"],
        },
    }

def build_failure_rate(changes):
    """
    Calculate build & test pipeline failure rate from Gerrit comments.

    Supports comments such as:

        Patch Set 1: Verified+1
        Patch Set 1: Verified+1 Build+1 Code-Review+2
        Patch Set 1: Code-Review+2 SonarScan+1 Test-2

    Any CI label in the supported set with a numeric vote is counted.
    Only +/-1 and +/-2 votes are treated as valid outcomes; +0 and other
    magnitudes are ignored.
    """

    header_pattern = re.compile(r"^Patch Set \d+:")
    vote_pattern = re.compile(r"([A-Za-z][A-Za-z0-9-]*)\s*([+-]\d+)")

    CI_LABELS = {
        "Verified",
        "Build",
        "Code-Review",
        "SonarScan",
        "Test",
    }

    total_outcomes = 0
    failed_outcomes = 0
    changes_with_builds = 0
    changes_with_failures = 0
    by_label = {}

    for change in changes:
        change_has_build = False
        change_has_failure = False

        for comment in change.get("comments", []):
            first_line = comment.get("message", "").split("\n")[0].strip()

            if not header_pattern.match(first_line):
                continue

            for label, vote in vote_pattern.findall(first_line):
                if label not in CI_LABELS:
                    continue

                vote_value = int(vote)
                if vote_value not in (-2, -1, 1, 2):
                    continue

                total_outcomes += 1
                change_has_build = True

                if vote_value < 0:
                    failed_outcomes += 1
                    change_has_failure = True

                stats = by_label.setdefault(
                    label,
                    {
                        "total": 0,
                        "failed": 0,
                    },
                )

                stats["total"] += 1

                if vote_value < 0:
                    stats["failed"] += 1

        if change_has_build:
            changes_with_builds += 1

        if change_has_failure:
            changes_with_failures += 1

    if changes_with_builds == 0:
        return None

    return {
        "total_changes_with_builds": changes_with_builds,
        "total_outcomes": total_outcomes,
        "failed_outcomes": failed_outcomes,
        "overall_failure_rate": round(
            failed_outcomes / total_outcomes * 100,
            2,
        ) if total_outcomes else 0,
        "changes_with_failures": changes_with_failures,
        "changes_failure_rate": round(
            changes_with_failures / changes_with_builds * 100,
            2,
        ) if changes_with_builds else 0,
        "by_label": {
            label: {
                "total": stats["total"],
                "failed": stats["failed"],
                "failure_rate": round(
                    stats["failed"] / stats["total"] * 100,
                    2,
                ) if stats["total"] else 0,
            }
            for label, stats in by_label.items()
        },
    }
def summarize_change_metrics(developer, dev_changes, reviewer_changes, commenter_changes):
    return {
        "change_count": len(dev_changes),
        "average_patchsets": _average_patchsets(dev_changes),
        "review_requests_sent":_review_requests_sent(reviewer_changes, developer),
        "review_requests_received":_review_requests_received(dev_changes),
        "comments_sent": _comments_sent(commenter_changes,developer),
        "comments_received":_comments_received(dev_changes),
        "lead_time": _lead_time(dev_changes,debug=True),
        "build_failure_rate": build_failure_rate(dev_changes),
    }

def developer_snapshot_metrics(
    username,
    dev_changes=None,
    reviewer_changes=None,
    commenter_changes=None,
):

    dev_changes = dev_changes or []
    reviewer_changes = reviewer_changes or []
    commenter_changes = commenter_changes or []
    #to avoid redundant calls
    cbspr = _changes_by_status_per_repo(dev_changes)

    return {
        "change_count": len(dev_changes),
        "projects": projects_with_counts(cbspr),
        "changes_by_status_per_repo": cbspr,
        "average_patchsets": _average_patchsets(dev_changes),
        "review_requests_received":
            _review_requests_received(dev_changes),

        "review_requests_sent":
            _review_requests_sent(reviewer_changes, username),

        "comments_received":
            _comments_received(dev_changes),

        "comments_sent":
            _comments_sent(commenter_changes, username),

        "lead_time":
            _lead_time(dev_changes,debug=True),

        "reviewer_response_time":
            reviewer_response_time(reviewer_changes, username),

        "build_failure_rate":
            build_failure_rate(dev_changes),
    }    

def developer_performance_grouped(
    username,
    dev_changes,
    reviewer_changes,
    commenter_changes,
    group_by,
):

    if group_by == "project":
        key_func = lambda c: c.get("project") or "unknown"
    elif group_by == "topic":
        key_func = lambda c: c.get("topic") or "untagged"
    elif group_by == "owner":
        key_func = _normalize_owner 
    else:
        raise ValueError(f"Unknown group: {group_by}")

    grouped = defaultdict(list)
    for change in dev_changes:
        grouped[key_func(change)].append(change)

    result = {}

    for group_name, group_dev_changes in grouped.items():

        group_reviewer_changes = [
            c
            for c in reviewer_changes
            if key_func(c) == group_name
        ]

        group_commenter_changes = [
            c
            for c in commenter_changes
            if key_func(c) == group_name
        ]

        result[group_name] = developer_snapshot_metrics(
            username=username,
            dev_changes=group_dev_changes,
            reviewer_changes=group_reviewer_changes,
            commenter_changes=group_commenter_changes,
        )

    return result

def project_developer_metrics(
    owner_changes,
    reviewer_changes,
    commenter_changes,
):

    grouped = defaultdict(list)

    for change in owner_changes:
        grouped[_normalize_owner(change)].append(change)

    result = {}

    for username, dev_changes in grouped.items():

        review = [
            c
            for c in reviewer_changes
            if _normalize_owner(c) == username
        ]

        comments = [
            c
            for c in commenter_changes
            if _normalize_owner(c) == username
        ]

        result[username] = developer_snapshot_metrics(
            username=username,
            dev_changes=dev_changes,
            reviewer_changes=review,
            commenter_changes=comments,
        )

    return result

def split_changes_for_developer(changes, username):

    dev_changes = []
    reviewer_changes = []
    commenter_changes = []

    for change in changes:

        owner = _normalize_owner(change)

        if owner == username:
            dev_changes.append(change)

        reviewers = {
            reviewer.get("username")
            for reviewer in change.get("allReviewers", [])
            if reviewer.get("username") not in (None, "jenkins")
        }

        if username in reviewers:
            reviewer_changes.append(change)

        if any(
            comment.get("reviewer", {}).get("username") == username
            for comment in change.get("comments", [])
        ):
            commenter_changes.append(change)

    return (
        dev_changes,
        reviewer_changes,
        commenter_changes,
    )