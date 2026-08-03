import json
import requests

from config import (
    GERRIT_HOST,
    GERRIT_USER,
    GERRIT_HTTP_PASSWORD,
)

from concurrent.futures import ThreadPoolExecutor

def enrich_reviewer_updates(changes, max_workers=10):
    """
    Fetch reviewer_updates for every change in parallel.
    """

    def load(change):

        reviewers = {
            r.get("username")
            for r in change.get("allReviewers", [])
        }

        if "jenkins" in reviewers and len(reviewers) == 1:
            change["reviewer_updates"] = []
            return change

        detail = fetch_change_detail(change["number"])

        change["reviewer_updates"] = detail.get(
            "reviewer_updates",
            []
        )

        return change

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(load, changes))
    
def fetch_change_detail(change_number: int) -> dict:

    response = requests.get(
        f"https://{GERRIT_HOST}/a/changes/{change_number}/detail",
        auth=(GERRIT_USER, GERRIT_HTTP_PASSWORD),
        verify=False,
        timeout=30,
    )

    response.raise_for_status()

    text = response.text

    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]

    return json.loads(text)