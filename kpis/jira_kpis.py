def calculate_issue_metrics(issues):
    total = len(issues)

    completed = [
        issue
        for issue in issues
        if issue["status_category"] == "Done"
    ]

    bugs = [
        issue
        for issue in issues
        if issue["issue_type"] == "Bug"
    ]

    return {
        "total_issues": total,
        "completed": len(completed),
        "open": total - len(completed),
        "bugs": len(bugs),
    }