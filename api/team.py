from fastapi import APIRouter

from database.crud import get_latest_team_snapshot

router = APIRouter()


@router.get("/team/graph")
def team_graph():

    return get_latest_team_snapshot()