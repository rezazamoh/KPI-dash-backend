from clients.file_loader import load_json

from database.crud import (
    upsert_gerrit_change
)

changes = load_json(
    "data/gerrit.json"
)

for change in changes:

    upsert_gerrit_change(change)

print(
    f"Loaded {len(changes)} changes"
)