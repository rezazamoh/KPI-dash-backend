"""
Gerrit change/review analytics.

Structure:
    - Constants:            shared literals (excluded usernames, statuses, CI labels)
    - Low-level stat helpers: generic aggregation over counters/values
    - Gerrit-domain parsing:  extracting owner/timestamps/votes from raw change dicts
    - Aggregation/orchestration: building per-developer / per-project snapshots
"""

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import NamedTuple, Optional
import re


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Service accounts / bots excluded from "who reviewed / commented" stats.
EXCLUDED_USERNAMES = {"jenkins"}

STATUS_MERGED = "MERGED"
STATUS_UNKNOWN = "UNKNOWN"

# CI/label names counted as build/test outcomes in build_failure_rate().
CI_LABELS = {
    "Verified",
    "Build",
    "Code-Review",
    "SonarScan",
    "Test",
}

# Only these vote magnitudes are treated as a valid pass/fail outcome;
# +0 and other magnitudes are ignored.
VALID_VOTE_VALUES = {-2, -1, 1, 2}

_HEADER_PATTERN = re.compile(r"^Patch Set \d+:")
_VOTE_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9-]*)\s*([+-]\d+)")

# Gerrit's reviewer-update timestamp format, e.g. "2024-01-02 03:04:05.123000".
# The trailing "000" pads microseconds out to a fixed 6-digit field so
# strptime's %f (which expects exactly 6 digits) parses it correctly.
_GERRIT_TS_FORMAT = "%Y-%m-%d %H:%M:%S.%f000"


class ChangeSet(NamedTuple):
    """The three change lists needed to compute metrics for one person/group."""

    dev_changes: list
    reviewer_changes: list
    commenter_changes: list


# ---------------------------------------------------------------------------
# Low-level stat helpers
# ---------------------------------------------------------------------------

def _people_stats(
    counter: dict,
    change_counts: list,
    by_person_label: dict | None = None,
) -> dict:
    """
    Turn a {username: count} counter into a ranked people list.

    Existing fields are preserved:
        people[].username
        people[].count
        stats.per_person
        stats.per_change

    Additional review-analysis fields:
        people[].by_label
        stats.by_label

    `stats.by_label` contains both label-level rates and vote-value
    distributions. The label `rate` is relative to all review votes.
    Each vote value has:
        - total: number of occurrences
        - rate: percentage of all review votes
        - value_rate: percentage within that label
    """

    if not counter:
        return {
            "people": [],
            "stats": None,
        }

    people = []

    for username, count in sorted(
        counter.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        person = {
            "username": username,
            "count": count,
        }

        if by_person_label and username in by_person_label:
            person["by_label"] = by_person_label[username]

        people.append(person)

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

    # Aggregate review votes across all people.
    if by_person_label:
        aggregate_labels = {}

        for person_labels in by_person_label.values():
            for label, label_stats in person_labels.items():
                aggregate = aggregate_labels.setdefault(
                    label,
                    {
                        "total": 0,
                        "values": defaultdict(int),
                    },
                )

                aggregate["total"] += label_stats["total"]

                for value, count in label_stats["values"].items():
                    aggregate["values"][value] += count

        total_reviews = sum(
            label_stats["total"]
            for label_stats in aggregate_labels.values()
        )

        stats["by_label"] = {}

        for label, label_stats in aggregate_labels.items():
            label_total = label_stats["total"]

            stats["by_label"][label] = {
                "total": label_total,
                "rate": round(
                    label_total / total_reviews * 100,
                    2,
                ) if total_reviews else 0,
                "values": {
                    value: {
                        "total": count,
                        "rate": round(
                            count / total_reviews * 100,
                            2,
                        ) if total_reviews else 0,
                        "value_rate": round(
                            count / label_total * 100,
                            2,
                        ) if label_total else 0,
                    }
                    for value, count in sorted(
                        label_stats["values"].items(),
                        key=lambda x: int(x[0]),
                        reverse=True,
                    )
                },
            }

    return {
        "people": people,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Gerrit-domain parsing
# ---------------------------------------------------------------------------

def _normalize_owner(change: dict) -> Optional[str]:
    owner = change.get("owner")

    if isinstance(owner, dict):
        return owner.get("username") or owner.get("name")

    return owner


def _reviewer_added_ts(change: dict, username: str) -> Optional[int]:
    """Return the timestamp when `username` was added as a reviewer."""

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
            datetime.strptime(ts, _GERRIT_TS_FORMAT).timestamp()
        )

        if earliest is None or ts < earliest:
            earliest = ts

    return earliest


def _changes_by_status_per_repo(changes: list) -> dict:
    """
    Group changes by status -> repo, returning a count per repo per status.

    Args:
        changes: List of Gerrit change dicts

    Returns:
        dict: { status: { repo: count } }
    """
    result = defaultdict(lambda: defaultdict(int))
    for c in changes:
        status = c.get("status", STATUS_UNKNOWN)
        repo = c.get("project", "unknown")
        result[status][repo] += 1
    return {
        status: dict(repos)
        for status, repos in result.items()
    }


def build_failure_rate(changes: list) -> Optional[dict]:
    """
    Calculate build & test pipeline failure rate from Gerrit comments.

    Supports comments such as:

        Patch Set 1: Verified+1
        Patch Set 1: Verified+1 Build+1 Code-Review+2
        Patch Set 1: Code-Review+2 SonarScan+1 Test-2

    Any CI label in CI_LABELS with a numeric vote is counted. Only votes
    in VALID_VOTE_VALUES are treated as valid outcomes.
    """

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

            if not _HEADER_PATTERN.match(first_line):
                continue

            for label, vote in _VOTE_PATTERN.findall(first_line):
                if label not in CI_LABELS:
                    continue

                vote_value = int(vote)
                if vote_value not in VALID_VOTE_VALUES:
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


# ---------------------------------------------------------------------------
# Per-metric aggregations
# ---------------------------------------------------------------------------

def projects_with_counts(changes_by_status_per_repo: dict) -> list:
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


def _average_patchsets(changes: list):
    if not changes:
        return 0

    return round(
        mean(
            c.get("currentPatchSet", {}).get("number", 0)
            for c in changes
        ),
        2
    )

def _patchset_gap_time(changes: list, debug: bool = False) -> Optional[dict]:
    """
    Calculate time between consecutive patchsets uploaded by the developer.

    For each change, its patchsets are sorted by creation time and the gap
    (in seconds) between each patchset and the next is recorded. Returns the
    min/mean/max gap across all changes, or None if no change has >= 2
    patchsets with a creation timestamp.

    Args:
        changes: Developer's changes.
        debug: If True, include the min/max change URLs for verification.
    """

    gaps = []

    for change in changes:
        patchsets = change.get("patchSets", [])

        if not isinstance(patchsets, list) or not patchsets:
            continue

        ts_list = sorted(
            ps.get("createdOn")
            for ps in patchsets
            if isinstance(ps, dict) and ps.get("createdOn")
        )

        if len(ts_list) < 2:
            continue

        for prev, curr in zip(ts_list, ts_list[1:]):
            gaps.append(
                {
                    "duration": curr - prev,
                    "url": change.get("url"),
                    "change_number": change.get("number"),
                }
            )

    if not gaps:
        return None

    gaps.sort(key=lambda x: x["duration"])

    values = [x["duration"] for x in gaps]

    if not debug:
        return {
            "min": round(values[0], 2),
            "mean": round(mean(values), 2),
            "max": round(values[-1], 2),
        }

    return {
        "min": {
            "duration": round(gaps[0]["duration"], 2),
            "url": gaps[0]["url"],
            "change_number": gaps[0]["change_number"],
        },
        "mean": round(mean(values), 2),
        "max": {
            "duration": round(gaps[-1]["duration"], 2),
            "url": gaps[-1]["url"],
            "change_number": gaps[-1]["change_number"],
        },
    }

def _review_vote_stats(change: dict, username: str) -> dict:
    """
    Extract review label/vote activity made by `username` from change
    comments.

    Expected comment format:

        Patch Set 3: Code-Review+2
        Patch Set 4: Code-Review-1 Verified+1

    Returns:

        {
            "Code-Review": {
                "total": 2,
                "positive": 1,
                "negative": 1,
                "values": {
                    "2": 1,
                    "-1": 1,
                },
            }
        }
    """

    by_label = {}

    for comment in change.get("comments", []):
        reviewer = comment.get("reviewer")

        if not isinstance(reviewer, dict):
            continue

        if reviewer.get("username") != username:
            continue

        first_line = comment.get("message", "").split("\n")[0].strip()

        if not _HEADER_PATTERN.match(first_line):
            continue

        for label, vote in _VOTE_PATTERN.findall(first_line):
            vote_value = int(vote)

            if vote_value not in VALID_VOTE_VALUES:
                continue

            label_stats = by_label.setdefault(
                label,
                {
                    "total": 0,
                    "positive": 0,
                    "negative": 0,
                    "values": defaultdict(int),
                },
            )

            label_stats["total"] += 1
            label_stats["values"][str(vote_value)] += 1

            if vote_value > 0:
                label_stats["positive"] += 1
            else:
                label_stats["negative"] += 1

    for label_stats in by_label.values():
        label_stats["values"] = dict(label_stats["values"])

    return by_label

def _merge_person_label_stats(target: dict, source: dict) -> None:
    """Merge label-level vote statistics into a person's existing stats."""

    for label, source_stats in source.items():
        target_stats = target.setdefault(
            label,
            {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "values": defaultdict(int),
            },
        )

        target_stats["total"] += source_stats["total"]
        target_stats["positive"] += source_stats["positive"]
        target_stats["negative"] += source_stats["negative"]

        for value, count in source_stats["values"].items():
            target_stats["values"][value] += count


def _finalize_person_label_stats(by_person_label: dict) -> None:
    """Convert defaultdict instances to normal dicts for JSON output."""

    for person_labels in by_person_label.values():
        for label_stats in person_labels.values():
            label_stats["values"] = dict(label_stats["values"])


def _review_requests_received(dev_changes: list) -> dict:
    """
    Analyze reviews received on changes owned by the developer.

    Existing semantics are preserved:
        people[].count = number of changes on which the reviewer appears
                         in allReviewers.

    Additional data:
        people[].by_label = actual approval/vote activity by that reviewer.
    """

    change_review_counts = []
    reviewers = defaultdict(int)
    by_person_label = defaultdict(dict)

    for change in dev_changes:
        owner = _normalize_owner(change)
        change_reviewers = set()

        for reviewer in change.get("allReviewers", []):
            if not isinstance(reviewer, dict):
                continue

            username = reviewer.get("username")

            if (
                not username
                or username == owner
                or username in EXCLUDED_USERNAMES
            ):
                continue

            reviewers[username] += 1
            change_reviewers.add(username)

        for username in change_reviewers:
            label_stats = _review_vote_stats(change, username)

            if label_stats:
                _merge_person_label_stats(
                    by_person_label[username],
                    label_stats,
                )

        change_review_counts.append(len(change_reviewers))

    _finalize_person_label_stats(by_person_label)

    return _people_stats(
        reviewers,
        change_review_counts,
        by_person_label,
    )


def _review_requests_sent(
    reviewer_changes: list,
    developer: str,
) -> dict:
    """
    Analyze reviews sent by `developer`.

    Existing semantics are preserved:
        people[].count = number of changes owned by that developer
                         that were reviewed by the current developer.

    Additional data:
        people[].by_label = actual approval/vote activity made by the
                            current developer on that owner's changes.
    """

    reviewer_changes = reviewer_changes or []

    owners = defaultdict(int)
    by_person_label = defaultdict(dict)

    for change in reviewer_changes:
        owner = _normalize_owner(change)

        if not owner or owner == developer:
            continue

        owners[owner] += 1

        label_stats = _review_vote_stats(change, developer)

        if label_stats:
            _merge_person_label_stats(
                by_person_label[owner],
                label_stats,
            )

    _finalize_person_label_stats(by_person_label)

    return _people_stats(
        owners,
        [],
        by_person_label,
    )


def _comments_received(dev_changes: list) -> dict:
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

            if not username or username == owner or username in EXCLUDED_USERNAMES:
                continue

            commenters[username] += 1
            count += 1
        change_comment_counts.append(count)

    return _people_stats(commenters, change_comment_counts)


def _comments_sent(commenter_changes: list, developer: str) -> dict:
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

    return _people_stats(owners, [])


def reviewer_response_time(changes: list, username: str) -> Optional[dict]:
    """
    Calculate how long it takes `username` to respond after being added
    as a reviewer.

    A response is the earliest of:
      - a review comment
      - an approval/vote

    Returns min/mean/max response time as raw timestamp differences.
    """

    response_times = []

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
            response_times.append(first_activity - added_ts)

    if not response_times:
        return None

    return {
        "min": round(min(response_times), 2),
        "mean": round(mean(response_times), 2),
        "max": round(max(response_times), 2),
    }


def _lead_time(changes: list, debug: bool = False) -> Optional[dict]:
    """
    Calculate lead time (change creation -> merge) as a raw timestamp
    difference.

    Args:
        changes: Developer's changes.
        debug: If True, include the min/max change URLs for verification.
    """

    lead_times = []

    for change in changes:
        if change.get("status") != STATUS_MERGED:
            continue

        created_ts = change.get("createdOn")
        updated_ts = change.get("lastUpdated")

        if not created_ts or not updated_ts:
            continue

        created = datetime.fromtimestamp(created_ts)
        updated = datetime.fromtimestamp(updated_ts)
        duration = (updated - created).total_seconds()

        lead_times.append(
            {
                "duration": duration,
                "url": change.get("url"),
                "change_number": change.get("number"),
            }
        )

    if not lead_times:
        return None

    lead_times.sort(key=lambda x: x["duration"])

    values = [x["duration"] for x in lead_times]

    if not debug:
        return {
            "min": round(values[0], 2),
            "mean": round(mean(values), 2),
            "max": round(values[-1], 2),
        }

    return {
        "min": {
            "duration": round(lead_times[0]["duration"], 2),
            "url": lead_times[0]["url"],
            "change_number": lead_times[0]["change_number"],
        },
        "mean": round(mean(values), 2),
        "max": {
            "duration": round(lead_times[-1]["duration"], 2),
            "url": lead_times[-1]["url"],
            "change_number": lead_times[-1]["change_number"],
        },
    }


def hotspot_files(changes: list, limit: int = 10) -> list:
    files = defaultdict(
        lambda: {
            "change_count": 0,
            "patchset_count": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "_changes": set(),
        }
    )

    for change in changes:
        change_id = change.get("id")

        for patchset in change.get("patchSets", []):
            for file_info in patchset.get("files", []):
                filename = file_info.get("file")

                if not filename or filename == "/COMMIT_MSG":
                    continue

                entry = files[filename]

                # This file appeared in this patchset
                entry["patchset_count"] += 1

                # Track unique Gerrit changes
                if change_id not in entry["_changes"]:
                    entry["_changes"].add(change_id)
                    entry["change_count"] += 1

                entry["lines_added"] += (
                    file_info.get("insertions") or 0
                )

                entry["lines_deleted"] += abs(
                    file_info.get("deletions") or 0
                )

    result = []

    for filename, metrics in files.items():
        result.append({
            "file": filename,
            "change_count": metrics["change_count"],
            "patchset_count": metrics["patchset_count"],
            "lines_added": metrics["lines_added"],
            "lines_deleted": metrics["lines_deleted"],
        })

    result.sort(
        key=lambda item: item["change_count"],
        reverse=True,
    )

    return result[:limit]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def summarize_change_metrics(developer: str, changeset: ChangeSet) -> dict:
    """
    The subset of a developer snapshot that doesn't need grouping/repo
    breakdowns or file hotspots. Used standalone, and as the base that
    developer_snapshot_metrics() extends.
    """
    dev_changes, reviewer_changes, commenter_changes = changeset

    return {
        "change_count": len(dev_changes),
        "changes_reviewed": len(reviewer_changes),
        "average_patchsets": _average_patchsets(dev_changes),
        "patchset_gap_time": _patchset_gap_time(dev_changes, debug=True),
        "review_requests_sent": _review_requests_sent(reviewer_changes, developer),
        "review_requests_received": _review_requests_received(dev_changes),
        "comments_sent": _comments_sent(commenter_changes, developer),
        "comments_received": _comments_received(dev_changes),
        "lead_time": _lead_time(dev_changes, debug=True),
        "build_failure_rate": build_failure_rate(dev_changes),
    }


def developer_snapshot_metrics(
    username: str,
    dev_changes: list = None,
    reviewer_changes: list = None,
    commenter_changes: list = None,
) -> dict:

    changeset = ChangeSet(
        dev_changes=dev_changes or [],
        reviewer_changes=reviewer_changes or [],
        commenter_changes=commenter_changes or [],
    )

    # to avoid redundant calls
    cbspr = _changes_by_status_per_repo(changeset.dev_changes)

    base = summarize_change_metrics(username, changeset)

    return {
        **base,
        "projects": projects_with_counts(cbspr),
        "changes_by_status_per_repo": cbspr,
        "reviewer_response_time": reviewer_response_time(
            changeset.reviewer_changes, username
        ),
        "file_hotspots": hotspot_files(changeset.dev_changes),
    }


def _group_key_func(group_by: str):
    if group_by == "project":
        return lambda c: c.get("project") or "unknown"
    if group_by == "topic":
        return lambda c: c.get("topic") or "untagged"
    if group_by == "owner":
        return _normalize_owner
    raise ValueError(f"Unknown group: {group_by}")


def developer_performance_grouped(
    username: str,
    dev_changes: list,
    reviewer_changes: list,
    commenter_changes: list,
    group_by: str,
) -> dict:

    key_func = _group_key_func(group_by)

    grouped = defaultdict(list)
    for change in dev_changes:
        grouped[key_func(change)].append(change)

    result = {}

    for group_name, group_dev_changes in grouped.items():
        group_reviewer_changes = [
            c for c in reviewer_changes if key_func(c) == group_name
        ]
        group_commenter_changes = [
            c for c in commenter_changes if key_func(c) == group_name
        ]

        # When grouping by "owner", each group *is* a developer, so the
        # snapshot's username should be that developer, not the outer
        # `username` argument (which doesn't apply per-group here).
        snapshot_username = group_name if group_by == "owner" else username

        result[group_name] = developer_snapshot_metrics(
            username=snapshot_username,
            dev_changes=group_dev_changes,
            reviewer_changes=group_reviewer_changes,
            commenter_changes=group_commenter_changes,
        )

    return result


def project_developer_metrics(
    owner_changes: list,
    reviewer_changes: list,
    commenter_changes: list,
) -> dict:
    """
    Per-owner breakdown of `owner_changes` (i.e. grouping by "owner").
    Thin wrapper around developer_performance_grouped() so the two grouping
    paths share one implementation. `username` is unused for owner-grouping
    since each group's own key is used as the snapshot username.
    """
    return developer_performance_grouped(
        username=None,
        dev_changes=owner_changes,
        reviewer_changes=reviewer_changes,
        commenter_changes=commenter_changes,
        group_by="owner",
    )


def split_changes_for_developer(changes: list, username: str) -> ChangeSet:

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
            if reviewer.get("username") not in ({None} | EXCLUDED_USERNAMES)
        }

        if username in reviewers:
            reviewer_changes.append(change)

        if any(
            comment.get("reviewer", {}).get("username") == username
            for comment in change.get("comments", [])
        ):
            commenter_changes.append(change)

    return ChangeSet(dev_changes, reviewer_changes, commenter_changes)