from fastapi import APIRouter

from database.db import SessionLocal
from database.kpi_models import TeamSnapshot

router = APIRouter()

@router.get("/team/graph")
def team_graph():

    db = SessionLocal()

    snapshot = (
        db.query(TeamSnapshot)
        .order_by(
            TeamSnapshot.snapshot_time.desc()
        )
        .first()
    )

    db.close()

    if not snapshot:
        return {}

    return snapshot.metrics_json