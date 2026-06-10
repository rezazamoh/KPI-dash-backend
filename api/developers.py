from fastapi import APIRouter
from database.crud import get_developer_metrics
from database.db import SessionLocal
from database.crud import (
    get_all_developers,
    get_latest_snapshot
)

router = APIRouter()


@router.get("/developers")
def developers():

    return get_all_developers()

@router.get("/developers/{username}")
def developer(username):

    snapshot = get_latest_snapshot(
        username
    )

    if not snapshot:

        return {
            "error": "developer not found"
        }

    return {
    "username": username,
    "snapshot_time": snapshot.snapshot_time,
    "metrics": snapshot.metrics_json
}