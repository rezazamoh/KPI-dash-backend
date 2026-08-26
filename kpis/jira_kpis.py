from collections import Counter
from datetime import datetime, timezone


def _parse_jira_date(value):
    if not value:
        return None

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def calculate_issue_metrics(issues):
    now = datetime.now(timezone.utc)

    total = len(issues)

    completed = []
    bugs = []

    status_counts = Counter()
    issue_type_counts = Counter()
    priority_counts = Counter()
    assignee_counts = Counter()
    reporter_counts = Counter()
    component_counts = Counter()
    label_counts = Counter()
    fix_version_counts = Counter()

    resolution_times = []
    ages = []

    for issue in issues:
        fields = issue.get("fields", {})

        # -------------------------
        # Basic fields
        # -------------------------

        status = fields.get("status") or {}
        status_name = status.get("name")
        status_category = status.get("statusCategory") or {}
        status_category_name = status_category.get("name")

        issue_type = fields.get("issuetype") or {}
        issue_type_name = issue_type.get("name")

        priority = fields.get("priority") or {}
        priority_name = priority.get("name")

        # -------------------------
        # Counts
        # -------------------------

        if status_name:
            status_counts[status_name] += 1

        if issue_type_name:
            issue_type_counts[issue_type_name] += 1

        if priority_name:
            priority_counts[priority_name] += 1

        # -------------------------
        # Completed
        # -------------------------

        if status_category_name == "Done":
            completed.append(issue)

        # -------------------------
        # Bugs
        # -------------------------

        if issue_type_name == "Bug":
            bugs.append(issue)

        # -------------------------
        # Assignee
        # -------------------------

        assignee = fields.get("assignee")

        if assignee:
            name = (
                assignee.get("displayName")
                or assignee.get("name")
                or assignee.get("key")
            )

            if name:
                assignee_counts[name] += 1

        # -------------------------
        # Reporter
        # -------------------------

        reporter = fields.get("reporter")

        if reporter:
            name = (
                reporter.get("displayName")
                or reporter.get("name")
                or reporter.get("key")
            )

            if name:
                reporter_counts[name] += 1

        # -------------------------
        # Components
        # -------------------------

        for component in fields.get("components") or []:
            name = component.get("name")

            if name:
                component_counts[name] += 1

        # -------------------------
        # Labels
        # -------------------------

        for label in fields.get("labels") or []:
            label_counts[label] += 1

        # -------------------------
        # Fix versions
        # -------------------------

        for version in fields.get("fixVersions") or []:
            name = version.get("name")

            if name:
                fix_version_counts[name] += 1

        # -------------------------
        # Dates
        # -------------------------

        created = _parse_jira_date(
            fields.get("created")
        )

        updated = _parse_jira_date(
            fields.get("updated")
        )

        resolution_date = _parse_jira_date(
            fields.get("resolutiondate")
        )

        # Issue age
        if created:
            age = (now - created).total_seconds()

            ages.append(age)

        # Resolution time
        if created and resolution_date:
            resolution_time = (
                resolution_date - created
            ).total_seconds()

            resolution_times.append(resolution_time)

    # -------------------------
    # Derived metrics
    # -------------------------

    completed_count = len(completed)
    bug_count = len(bugs)

    open_count = total - completed_count

    completion_rate = (
        completed_count / total * 100
        if total
        else 0
    )

    bug_rate = (
        bug_count / total * 100
        if total
        else 0
    )

    average_age = (
        sum(ages) / len(ages)
        if ages
        else None
    )

    average_resolution_time = (
        sum(resolution_times) / len(resolution_times)
        if resolution_times
        else None
    )

    return {
        "total_issues": total,

        "completed": completed_count,
        "open": open_count,

        "completion_rate": round(
            completion_rate,
            2,
        ),

        "bugs": bug_count,
        "bug_rate": round(
            bug_rate,
            2,
        ),

        "average_issue_age": (
            round(average_age, 2)
            if average_age is not None
            else None
        ),

        "average_resolution_time": (
            round(average_resolution_time, 2)
            if average_resolution_time is not None
            else None
        ),

        "by_status": dict(status_counts),
        "by_issue_type": dict(issue_type_counts),
        "by_priority": dict(priority_counts),

        "by_assignee": dict(assignee_counts),
        "by_reporter": dict(reporter_counts),

        "by_component": dict(component_counts),
        "by_label": dict(label_counts),
        "by_fix_version": dict(fix_version_counts),
    }