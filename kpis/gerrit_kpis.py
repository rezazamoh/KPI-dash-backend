from collections import defaultdict, Counter
from statistics import mean


def changes_per_repo(changes):

    result = defaultdict(lambda: defaultdict(int))

    for c in changes:

        dev = c["owner"]["username"]
        repo = c["project"]

        result[dev][repo] += 1

    return {
        dev: dict(repos)
        for dev, repos in result.items()
    }


def mean_patchsets(changes):

    stats = defaultdict(list)

    for c in changes:

        dev = c["owner"]["username"]

        stats[dev].append(
            len(c.get("patchSets", []))
        )

    return {
        dev: round(mean(v), 2)
        for dev, v in stats.items()
    }


def comments_sent(changes):

    counter = Counter()

    for c in changes:

        for cm in c.get("comments", []):

            reviewer = cm.get("reviewer", {})
            username = reviewer.get("username")

            if username:
                counter[username] += 1

    return dict(counter)


def comments_received(changes):

    counter = Counter()

    for c in changes:

        owner = c["owner"]["username"]

        counter[owner] += len(
            c.get("comments", [])
        )

    return dict(counter)


def review_requests_sent(changes):

    counter = Counter()

    for c in changes:

        owner = c["owner"]["username"]

        for reviewer in c.get(
            "allReviewers",
            []
        ):

            username = reviewer.get(
                "username"
            )

            if (
                username and
                username != owner
            ):
                counter[owner] += 1

    return dict(counter)


def review_requests_received(changes):

    counter = Counter()

    for c in changes:

        for reviewer in c.get(
            "allReviewers",
            []
        ):

            username = reviewer.get(
                "username"
            )

            if username:
                counter[username] += 1

    return dict(counter)


def review_graph(changes):

    edges = Counter()

    for c in changes:

        author = c["owner"]["username"]

        for reviewer in c.get(
            "allReviewers",
            []
        ):

            username = reviewer.get(
                "username"
            )

            if (
                username and
                username != author
            ):
                edges[
                    (username, author)
                ] += 1

    return dict(edges)


def reviewer_response_time(changes):

    stats = defaultdict(list)

    for c in changes:

        created = c["createdOn"]

        first_seen = {}

        for cm in c.get("comments", []):

            reviewer = cm["reviewer"].get(
                "username"
            )

            ts = cm["timestamp"]

            if reviewer not in first_seen:
                first_seen[reviewer] = ts

        for reviewer, ts in first_seen.items():

            hours = (
                ts - created
            ) / 3600

            stats[reviewer].append(
                hours
            )

    result = {}

    for reviewer, values in stats.items():

        result[reviewer] = {
            "min": round(min(values), 2),
            "mean": round(mean(values), 2),
            "max": round(max(values), 2)
        }

    return result


def lead_time(changes):

    stats = defaultdict(list)

    for c in changes:

        hours = (
            c["lastUpdated"] -
            c["createdOn"]
        ) / 3600

        dev = c["owner"]["username"]

        stats[dev].append(hours)

    result = {}

    for dev, values in stats.items():

        result[dev] = {
            "min": round(min(values), 2),
            "mean": round(mean(values), 2),
            "max": round(max(values), 2)
        }

    return result


def complexity(changes):

    stats = defaultdict(list)

    for c in changes:

        total_lines = 0

        for ps in c.get(
            "patchSets",
            []
        ):

            total_lines += (
                ps.get(
                    "sizeInsertions",
                    0
                )
                +
                ps.get(
                    "sizeDeletions",
                    0
                )
            )

        score = (
            total_lines *
            max(
                len(
                    c.get(
                        "patchSets",
                        []
                    )
                ),
                1
            )
        )

        dev = c["owner"]["username"]

        stats[dev].append(score)

    return {
        dev: round(mean(v), 2)
        for dev, v in stats.items()
    }


def _normalize_owner(change):
    owner = change.get("owner", {})
    return owner.get("username", "unknown")


def _normalize_topic(change):
    topic = change.get("topic")
    return topic if topic else "untagged"


def _aggregate_performance(records):
    totals = {
        "change_count": len(records),
        "patchset_count": 0,
        "lead_time_hours": [],
        "complexity": [],
        "total_comments": 0,
        "reviewer_counts": [],
        "status_counts": {}
    }

    for change in records:
        totals["patchset_count"] += len(change.get("patchSets", []))

        created = change.get("createdOn", 0)
        updated = change.get("lastUpdated", created)
        if created and updated:
            totals["lead_time_hours"].append(
                (updated - created) / 3600
            )

        complexity = 0
        for ps in change.get("patchSets", []):
            complexity += (
                ps.get("sizeInsertions", 0)
                + ps.get("sizeDeletions", 0)
            )

        totals["complexity"].append(complexity)
        totals["total_comments"] += len(change.get("comments", []))

        reviewer_count = 0
        for reviewer in change.get("allReviewers", []):
            if reviewer.get("username"):
                reviewer_count += 1

        totals["reviewer_counts"].append(reviewer_count)

        status = change.get("status") or "unknown"
        totals["status_counts"][status] = (
            totals["status_counts"].get(status, 0) + 1
        )

    average = lambda values: round(mean(values), 2) if values else 0

    return {
        "change_count": totals["change_count"],
        "average_patchsets": round(
            totals["patchset_count"] / totals["change_count"], 2
        ) if totals["change_count"] else 0,
        "average_lead_time_hours": average(totals["lead_time_hours"]),
        "average_complexity": average(totals["complexity"]),
        "total_comments": totals["total_comments"],
        "average_reviewers_per_change": average(totals["reviewer_counts"]),
        "status_counts": totals["status_counts"]
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
            owner: _aggregate_performance(changes_by_dev)
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
            owner: _aggregate_performance(changes_by_dev)
            for owner, changes_by_dev in owners.items()
        }
        for change_topic, owners in result.items()
    }


def developer_performance_by_developer_repo(changes, username=None, repo=None, topic=None):
    """
    Aggregate performance grouped by owner -> project.
    Applies optional filters: username, repo, topic.
    """
    result = defaultdict(lambda: defaultdict(list))

    for change in changes:
        owner = _normalize_owner(change)
        if username and owner != username:
            continue

        project = change.get("project") or "unknown"
        if repo and project != repo:
            continue

        change_topic = _normalize_topic(change)
        if topic and change_topic != topic:
            continue

        result[owner][project].append(change)

    return {
        owner: {
            project: _aggregate_performance(changes_by_dev)
            for project, changes_by_dev in projects.items()
        }
        for owner, projects in result.items()
    }


def developer_performance_by_developer_topic(changes, username=None, topic=None, repo=None):
    """
    Aggregate performance grouped by owner -> topic.
    Applies optional filters: username, topic, repo.
    """
    result = defaultdict(lambda: defaultdict(list))

    for change in changes:
        owner = _normalize_owner(change)
        if username and owner != username:
            continue

        project = change.get("project") or "unknown"
        if repo and project != repo:
            continue

        change_topic = _normalize_topic(change)
        if topic and change_topic != topic:
            continue

        result[owner][change_topic].append(change)

    return {
        owner: {
            change_topic: _aggregate_performance(changes_by_dev)
            for change_topic, changes_by_dev in topics.items()
        }
        for owner, topics in result.items()
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