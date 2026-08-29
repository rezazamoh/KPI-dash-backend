import logs
import json

from api.utils import load_changes
from collectors.gerrit_rest import enrich_reviewer_updates


def export_mock_data():
    print("Loading changes from Gerrit...")

    changes = load_changes(
        live=True,
        options=[
            "--comments",
            "--current-patch-set",
            "--patch-sets",
            "--all-reviewers",
        ],
    )

    print(f"Loaded {len(changes)} changes")

    print("Enriching reviewer updates...")
    enrich_reviewer_updates(changes)

    print("Writing mock_data.json...")

    with open("mock_data.json", "w", encoding="utf-8") as f:
        json.dump(
            changes,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("Done.")


if __name__ == "__main__":
    export_mock_data()