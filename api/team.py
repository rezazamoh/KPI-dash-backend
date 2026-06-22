from fastapi import APIRouter, HTTPException, Query

from api.utils import load_changes, parse_date_range
from database.db import SessionLocal
from database.kpi_models import TeamSnapshot
from kpis.gerrit_kpis import review_comment_graph

router = APIRouter()


@router.get("/team/graph")
def team_graph(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    live: bool | None = Query(False)
):

    if live:
        changes = load_changes(
            start_date=start_date,
            end_date=end_date,
            live=True,
            options=["--all-reviewers", "--comments"],
        )
        return review_comment_graph(changes)

    parsed_start, parsed_end = parse_date_range(start_date, end_date)

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