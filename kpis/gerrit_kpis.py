from collections import defaultdict
from statistics import mean


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


def _review_requests_sent_stats(changes):
    stats = defaultdict(list)

    for change in changes:
        owner = _normalize_owner(change)
        count = sum(
            1
            for reviewer in change.get("allReviewers", [])
            if reviewer.get("username") and reviewer.get("username") != owner
        )
        stats[owner].append(count)

    return {
        owner: {
            "changes_count": len(counts),
            "total_requests": sum(counts),
            "min_requests_per_change": min(counts) if counts else 0,
            "mean_requests_per_change": round(mean(counts), 2) if counts else 0,
            "max_requests_per_change": max(counts) if counts else 0,
        }
        for owner, counts in stats.items()
    }


def _review_requests_received_stats(changes):
    stats = defaultdict(lambda: defaultdict(int))

    for change in changes:
        for reviewer in change.get("allReviewers", []):
            username = reviewer.get("username")
            if username:
                change_id = change.get("id") or change.get("change_number")
                stats[username][change_id] += 1

    return {
        username: {
            "changes_count": len(change_counts),
            "total_requests": sum(change_counts.values()),
            "min_requests_per_change": min(change_counts.values()) if change_counts else 0,
            "mean_requests_per_change": round(mean(change_counts.values()), 2) if change_counts else 0,
            "max_requests_per_change": max(change_counts.values()) if change_counts else 0,
        }
        for username, change_counts in stats.items()
    }


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


def _comments_received_stats(changes):
    stats = defaultdict(list)

    for change in changes:
        owner = _normalize_owner(change)
        stats[owner].append(len(change.get("comments", [])))

    return {
        owner: {
            "changes_count": len(counts),
            "total_comments": sum(counts),
            "min_comments_per_change": min(counts) if counts else 0,
            "mean_comments_per_change": round(mean(counts), 2) if counts else 0,
            "max_comments_per_change": max(counts) if counts else 0,
        }
        for owner, counts in stats.items()
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


def _lead_time_stats(changes):
    stats = defaultdict(list)

    for change in changes:
        owner = _normalize_owner(change)
        created = change.get("createdOn")
        submitted = change.get("submitted")
        updated = change.get("lastUpdated")
        end_ts = submitted or updated
        if created and end_ts:
            stats[owner].append((end_ts - created) / 3600)

    return {
        owner: {
            "min_hours": round(min(hours), 2) if hours else 0,
            "mean_hours": round(mean(hours), 2) if hours else 0,
            "max_hours": round(max(hours), 2) if hours else 0,
        }
        for owner, hours in stats.items()
    }


def summarize_change_metrics(changes):
    return {
        "change_count": len(changes),
        "average_patchsets": _average_patchsets(changes),
        "review_requests_sent": _review_requests_sent_stats(changes),
        "review_requests_received": _review_requests_received_stats(changes),
        "comments_sent": _comments_sent_stats(changes),
        "comments_received": _comments_received_stats(changes),
        "lead_time": _lead_time_stats(changes),
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


def developer_snapshot_metrics(changes, username, reviewer_changes=None):
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
        c for c in changes
        if _normalize_owner(c) == username
    ]
    
    if not dev_changes:
        empty = {
            "change_count": 0,
            "average_patchsets": 0,
            "review_requests_sent": 0,
            "review_requests_received": 0,
            "comments_sent": 0,
            "comments_received": 0,
            "lead_time": {},
            "reviewer_response_time": {"min_hours": 0, "mean_hours": 0, "max_hours": 0},
            "changes_by_status_per_repo": {},
        }
        if reviewer_changes:
            empty["reviewer_response_time"] = reviewer_response_time(reviewer_changes, username)
        return empty
    
    # Get full metrics for this developer's changes
    full_metrics = summarize_change_metrics(dev_changes)
    
    # Extract only this developer's stats from the nested structures
    review_sent = full_metrics.get("review_requests_sent", {}).get(username, {})
    review_received = full_metrics.get("review_requests_received", {}).get(username, {})
    comments_sent = full_metrics.get("comments_sent", {}).get(username, {})
    comments_received = full_metrics.get("comments_received", {}).get(username, {})
    lead = full_metrics.get("lead_time", {}).get(username, {})
    
    # Compute reviewer response time from reviewer changes
    resp_time = {"min_hours": 0, "mean_hours": 0, "max_hours": 0}
    if reviewer_changes:
        resp_time = reviewer_response_time(reviewer_changes, username)
    
    # Changes grouped by status and repo
    changes_per_status_repo = _changes_by_status_per_repo(dev_changes)
    
    return {
        "change_count": full_metrics["change_count"],
        "average_patchsets": full_metrics["average_patchsets"],
        "review_requests_sent": review_sent,
        "review_requests_received": review_received,
        "comments_sent": comments_sent,
        "comments_received": comments_received,
        "lead_time": lead,
        "reviewer_response_time": resp_time,
        "changes_by_status_per_repo": changes_per_status_repo,
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