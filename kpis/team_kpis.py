from collections import defaultdict


def build_team_graph(changes):

    edges = defaultdict(int)

    nodes = set()

    for change in changes:

        owner = change.get("owner", {}).get("username")

        nodes.add(owner)

        reviewers = change.get("allReviewers", [])

        for r in reviewers:

            reviewer = r.get("username")

            nodes.add(reviewer)

            edges[(owner, reviewer, "review")] += 1

    return {
        "nodes": list(nodes),
        "edges": [
            {
                "from": k[0],
                "to": k[1],
                "type": k[2],
                "count": v
            }
            for k, v in edges.items()
        ]
    }