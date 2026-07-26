from collections import defaultdict
from statistics import mean

def _people_stats(counter, change_counts):

    if not counter:
        return None

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

    result = {
        "people": people,
        "stats": {
            "per_person": {
                "min": min(person_values),
                "mean": round(mean(person_values), 2),
                "max": max(person_values),
            }
        },
    }

    if change_counts:
        result["stats"]["per_change"] = {
            "min": min(change_counts),
            "mean": round(mean(change_counts), 2),
            "max": max(change_counts),
        }

    return result

def _normalize_owner(change):
    owner = change.get("owner")

    if isinstance(owner, dict):
        return owner.get("username") or owner.get("name")
    
    return owner

def _normalize_topic(change):
    topic = change.get("topic")
    return topic if topic else "untagged"

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
    """Get the timestamp when `username` was added as a reviewer on a change."""
    sources = []
    cps = change.get("currentPatchSet")
    if cps and isinstance(cps, dict):
        sources.append(cps)
    for ps in change.get("patchSets", []):
        if isinstance(ps, dict):
            sources.append(ps)

    earliest = None
    for source in sources:
        for approval in source.get("approvals", []):
            by = approval.get("by", {})
            if isinstance(by, dict) and by.get("username") == username:
                ts = approval.get("grantedOn")
                if ts is not None:
                    if earliest is None or ts < earliest:
                        earliest = ts
    return earliest

def reviewer_response_time(changes, username):
    """
    Calculate how long it takes `username` to respond when added as a reviewer.
    Uses the first comment timestamp minus the timestamp when they were added
    as a reviewer (from approval entries). Returns min/mean/max hours.

    Args:
        changes: List of changes where `username` was a reviewer
        username: Developer username

    Returns:
        dict with min_hours, mean_hours, max_hours
    """
    hours = []

    for change in changes:
        added_ts = _reviewer_added_ts(change, username)
        if added_ts is None:
            continue

        first_comment_ts = None
        for comment in change.get("comments", []):
            reviewer = comment.get("reviewer", {}).get("username")
            ts = comment.get("timestamp")
            if reviewer == username and ts is not None:
                if first_comment_ts is None or ts < first_comment_ts:
                    first_comment_ts = ts

        if first_comment_ts is not None and first_comment_ts > added_ts:
            hours.append((first_comment_ts - added_ts) / 3600)

    if not hours:
        return None

    return {
        "min_hours": round(min(hours), 2),
        "mean_hours": round(mean(hours), 2),
        "max_hours": round(max(hours), 2),
    }

def _lead_time(dev_changes):

    durations = []

    for change in dev_changes:

        if change.get("status") != "MERGED":
            continue

        created = change.get("createdOn")
        submitted = change.get("lastUpdated")

        if created is None or submitted is None:
            continue

        durations.append(submitted - created)

    if not durations:
        return None

    return {
        "min": min(durations),
        "mean": round(mean(durations), 2),
        "max": max(durations),
    }

def build_failure_rate(changes):
    """
    Calculate build & test pipeline failure rate from Jenkins comments
    on Gerrit changes.

    Scans each change's comments for Jenkins reviewer entries and parses
    the vote labels (e.g. Verified+1, Build-1, Test-1) from the first
    line of each comment to determine build/test outcomes.

    This function is generic and works on any set of changes (filtered
    by developer, project, topic, etc.) so it can be reused across
    different API contexts.

    Args:
        changes: List of Gerrit change dicts (must include 'comments')

    Returns:
        dict with aggregate build failure statistics and per-label
        breakdown
    """
    import re
    pattern = re.compile(r'Patch Set \d+:\s*(\w+)([+-]\d+)\s*$')

    total_outcomes = 0
    failed_outcomes = 0
    changes_with_builds = 0
    changes_with_failures = 0
    by_label = {}

    for change in changes:
        change_has_build = False
        change_has_failure = False

        for comment in change.get("comments", []):
            if comment.get("reviewer", {}).get("username") != "jenkins":
                continue

            first_line = comment.get("message", "").split("\n")[0].strip()
            match = pattern.match(first_line)
            if not match:
                continue

            label = match.group(1)
            vote = match.group(2)

            if vote == "+1":
                total_outcomes += 1
                change_has_build = True
            elif vote == "-1":
                total_outcomes += 1
                failed_outcomes += 1
                change_has_build = True
                change_has_failure = True
            else:
                continue

            if label not in by_label:
                by_label[label] = {"total": 0, "failed": 0}
            by_label[label]["total"] += 1
            if vote == "-1":
                by_label[label]["failed"] += 1

        if change_has_build:
            changes_with_builds += 1
        if change_has_failure:
            changes_with_failures += 1

    return {
        "total_changes_with_builds": changes_with_builds,
        "total_outcomes": total_outcomes,
        "failed_outcomes": failed_outcomes,
        "overall_failure_rate": round(
            failed_outcomes / total_outcomes * 100, 2
        ) if total_outcomes else 0,
        "changes_with_failures": changes_with_failures,
        "changes_failure_rate": round(
            changes_with_failures / changes_with_builds * 100, 2
        ) if changes_with_builds else 0,
        "by_label": {
            label: {
                "total": stats["total"],
                "failed": stats["failed"],
                "failure_rate": round(
                    stats["failed"] / stats["total"] * 100, 2
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
        "lead_time": _lead_time(dev_changes),
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

    metrics = {
        "change_count": len(dev_changes),
        "changes_by_status_per_repo": _changes_by_status_per_repo(dev_changes),
        "average_patchsets": _average_patchsets(dev_changes),
        "build_failure_rate": build_failure_rate(dev_changes),
    }

    optional_metrics = {
        "review_requests_sent":
            _review_requests_sent(reviewer_changes, username),

        "review_requests_received":
            _review_requests_received(dev_changes),

        "comments_sent":
            _comments_sent(commenter_changes, username),

        "comments_received":
            _comments_received(dev_changes),

        "lead_time":
            _lead_time(dev_changes),

        "reviewer_response_time":
            reviewer_response_time(reviewer_changes, username),
    }

    for key, value in optional_metrics.items():
        if value is not None:
            metrics[key] = value

    return metrics

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
        key_func = _normalize_topic
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

def project_developer_metrics(changes):

    developers = sorted({

        _normalize_owner(change)

        for change in changes

        if _normalize_owner(change)

    })

    result = {}

    for username in developers:

        (
            dev_changes,
            reviewer_changes,
            commenter_changes,
        ) = split_changes_for_developer(
            changes,
            username,
        )

        result[username] = developer_snapshot_metrics(
            username,
            dev_changes,
            reviewer_changes,
            commenter_changes,
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

def review_comment_graph(changes):

    review_edges = defaultdict(int)
    comment_edges = defaultdict(int)

    for change in changes:

        owner = (
            change.get("owner", {})
            .get("username")
        )

        if not owner:
            continue

        for reviewer in change.get(
            "allReviewers",
            []
        ):

            reviewer_name = reviewer.get(
                "username"
            )

            if (
                not reviewer_name
                or reviewer_name == owner
            ):
                continue

            review_edges[
                (reviewer_name, owner)
            ] += 1

        for comment in change.get(
            "comments",
            []
        ):

            commenter = (
                comment.get(
                    "reviewer",
                    {}
                )
                .get("username")
            )

            if (
                not commenter
                or commenter == owner
            ):
                continue

            comment_edges[
                (commenter, owner)
            ] += 1

    return {
        "review_edges": [
            {
                "source": src,
                "target": dst,
                "count": count
            }
            for (src, dst), count
            in review_edges.items()
        ],

        "comment_edges": [
            {
                "source": src,
                "target": dst,
                "count": count
            }
            for (src, dst), count
            in comment_edges.items()
        ]
    }