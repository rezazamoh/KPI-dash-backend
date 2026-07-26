from collections import defaultdict
from statistics import mean

def _people_stats(counter, change_counts):

    people = [
        {
            "username": u,
            "count": c,
        }
        for u, c in sorted(
            counter.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]

    person_values = list(counter.values())

    return {
        "people": people,
        "stats": {

            "per_person": {
                "min": min(person_values) if person_values else 0,
                "mean": round(mean(person_values), 2) if person_values else 0,
                "max": max(person_values) if person_values else 0,
            },

            "per_change": {
                "min": min(change_counts) if change_counts else 0,
                "mean": round(mean(change_counts), 2) if change_counts else 0,
                "max": max(change_counts) if change_counts else 0,
            },
        },
    }

def _normalize_owner(change):
    owner = change.get("owner", {})
    return owner.get("username", "unknown")


def _normalize_topic(change):
    topic = change.get("topic")
    return topic if topic else "untagged"


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
        owner = change["owner"]["username"]

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
    change_review_counts = []

    for change in reviewer_changes:

        owner = change["owner"]["username"]

        if owner != developer:
            owners[owner] += 1

    return _people_stats(owners,change_review_counts)

def _comments_received(dev_changes):

    commenters = defaultdict(int)
    change_comment_counts = []

    for change in dev_changes:

        owner = change["owner"]["username"]
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

def _comments_sent_stats(changes):
    stats = defaultdict(lambda: defaultdict(int))

    for change in changes:
        for comment in change.get("comments", []):
            commenter = comment.get("reviewer", {}).get("username")
            if commenter:
                change_id = change.get("id") or change.get("change_number")
                stats[commenter][change_id] += 1

    return {
        username: {
            "changes_count": len(change_counts),
            "total_comments": sum(change_counts.values()),
            "min_comments_per_change": min(change_counts.values()) if change_counts else 0,
            "mean_comments_per_change": round(mean(change_counts.values()), 2) if change_counts else 0,
            "max_comments_per_change": max(change_counts.values()) if change_counts else 0,
        }
        for username, change_counts in stats.items()
    }


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
        return {"min_hours": 0, "mean_hours": 0, "max_hours": 0}

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
        return {
            "min": 0,
            "mean": 0,
            "max": 0,
        }

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


def summarize_change_metrics(dev_changes, developer, reviewer_changes=None):
    return {
        "change_count": len(dev_changes),
        "average_patchsets": _average_patchsets(dev_changes),
        "review_requests_sent":
            _review_requests_sent(
                reviewer_changes,
                developer,
            ),
        "review_requests_received":
            _review_requests_received(dev_changes),
        "comments_sent": _comments_sent_stats(dev_changes),
        "comments_received":
            _comments_received(dev_changes),
        "lead_time": _lead_time(dev_changes),
        "build_failure_rate": build_failure_rate(dev_changes),
    }


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


def developer_snapshot_metrics(dev_changes, username, reviewer_changes=None):
    """
    Compute KPI snapshot for a single developer.
    Used by both live mode and snapshot refresh jobs.
    Ensures consistent metrics regardless of data source.
    
    Args:
        changes: List of Gerrit changes where user is owner (from live fetch or DB)
        username: Developer username to filter by
        reviewer_changes: List of changes where user is a reviewer (for response time)
    
    Returns:
        dict: Metrics summary for this developer
    """
    # Filter changes by owner
    dev_changes = [
        c for c in dev_changes
        if _normalize_owner(c) == username
    ]
    
    if not dev_changes:
        empty = {
            "change_count": 0,
            "changes_by_status_per_repo": {},
            "average_patchsets": 0,
            "review_requests_sent": 0,
            "review_requests_received": 0,
            "comments_sent": 0,
            "comments_received": 0,
            "lead_time": {},
            "reviewer_response_time": {"min_hours": 0, "mean_hours": 0, "max_hours": 0},
            "build_failure_rate": build_failure_rate([]),
        }
        if reviewer_changes:
            empty["reviewer_response_time"] = reviewer_response_time(reviewer_changes, username)
        return empty
    
    # Get full metrics for this developer's changes
    full_metrics = summarize_change_metrics(dev_changes, username, reviewer_changes)
    review_sent = full_metrics["review_requests_sent"]
    review_received = full_metrics["review_requests_received"]
    comments_sent = full_metrics["comments_sent"]
    comments_received = full_metrics["comments_received"]
    lead = full_metrics["lead_time"]
    
    # Compute reviewer response time from reviewer changes
    resp_time = {"min_hours": 0, "mean_hours": 0, "max_hours": 0}
    if reviewer_changes:
        resp_time = reviewer_response_time(reviewer_changes, username)
    
    # Changes grouped by status and repo
    changes_per_status_repo = _changes_by_status_per_repo(dev_changes)
    
    return {
        "change_count": full_metrics["change_count"],
        "changes_by_status_per_repo": changes_per_status_repo,
        "average_patchsets": full_metrics["average_patchsets"],
        "review_requests_sent": review_sent,
        "review_requests_received": review_received,
        "comments_sent": comments_sent,
        "comments_received": comments_received,
        "lead_time": lead,
        "reviewer_response_time": resp_time,
        "build_failure_rate": full_metrics["build_failure_rate"],
    }

def developer_performance_by_repo(changes, username=None, repo=None, topic=None):
    """
    Aggregate performance grouped by project -> owner.
    Applies optional filters: username, repo, topic.
    """
    result = defaultdict(lambda: defaultdict(list))

    for change in changes:
        if username and _normalize_owner(change) != username:
            continue

        project = change.get("project") or "unknown"
        if repo and project != repo:
            continue

        change_topic = _normalize_topic(change)
        if topic and change_topic != topic:
            continue

        owner = _normalize_owner(change)
        result[project][owner].append(change)

    return {
        project: {
            owner: summarize_change_metrics(changes_by_dev)
            for owner, changes_by_dev in owners.items()
        }
        for project, owners in result.items()
    }


def developer_performance_by_topic(changes, username=None, topic=None, repo=None):
    """
    Aggregate performance grouped by topic -> owner.
    Applies optional filters: username, topic, repo.
    """
    result = defaultdict(lambda: defaultdict(list))

    for change in changes:
        if username and _normalize_owner(change) != username:
            continue

        project = change.get("project") or "unknown"
        if repo and project != repo:
            continue

        change_topic = _normalize_topic(change)
        if topic and change_topic != topic:
            continue

        owner = _normalize_owner(change)
        result[change_topic][owner].append(change)

    return {
        change_topic: {
            owner: summarize_change_metrics(changes_by_dev)
            for owner, changes_by_dev in owners.items()
        }
        for change_topic, owners in result.items()
    }


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