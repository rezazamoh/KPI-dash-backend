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