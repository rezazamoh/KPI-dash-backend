from kpis.gerrit_kpis import (
    developer_snapshot_metrics,
    review_comment_graph,
)

from database.crud import (save_snapshot, save_team_snapshot)
from database.crud import get_gerrit_changes


changes = get_gerrit_changes()

# Get distinct developers from changes
developers = set()
for change in changes:
    owner = change.get("owner", {})
    if isinstance(owner, dict):
        username = owner.get("username")
    else:
        username = str(owner)
    if username and username != "unknown":
        developers.add(username)

# Save snapshot for each developer using the same unified metric calculation
for username in developers:
    metrics = developer_snapshot_metrics(changes, username)
    save_snapshot(
        username=username,
        metrics=metrics
    )

# Save team graph snapshot
graph = review_comment_graph(changes)

save_team_snapshot(graph)