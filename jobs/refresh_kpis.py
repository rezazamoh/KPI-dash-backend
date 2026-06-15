from collections import defaultdict

from kpis.gerrit_kpis import (
    mean_patchsets,
    comments_sent,
    comments_received,
    review_requests_sent,
    review_requests_received,
    changes_per_repo,
    lead_time,
    complexity,
    review_comment_graph,
)

from database.crud import (save_snapshot , save_team_snapshot)
from database.crud import get_all_gerrit_changes


changes = get_all_gerrit_changes()
print(changes[0].keys())
developers = defaultdict(lambda: {
    "basic": {},
    "communication": {},
    "review_flow": {},
    "delivery": {},
    "code_quality": {},
    "repos": {}
})

#BASIC
for u, v in mean_patchsets(changes).items():
    developers[u]["basic"]["mean_patchsets"] = v

#COMMS
for u, v in comments_sent(changes).items():
    developers[u]["communication"]["comments_sent"] = v

for u, v in comments_received(changes).items():
    developers[u]["communication"]["comments_received"] = v

for u, v in review_requests_sent(changes).items():
    developers[u]["communication"]["reviews_sent"] = v

for u, v in review_requests_received(changes).items():
    developers[u]["communication"]["reviews_received"] = v

#REPOS
for u, v in changes_per_repo(changes).items():
    developers[u]["repos"] = v

#DELIVERY
for u, v in lead_time(changes).items():
    developers[u]["delivery"]["lead_time"] = v

#QUALITY
for u, v in complexity(changes).items():
    developers[u]["code_quality"]["complexity"] = v

for username, metrics in developers.items():

    save_snapshot(
        username=username,
        metrics=metrics
    )
graph = review_comment_graph(
    changes
)

save_team_snapshot(
    graph
)