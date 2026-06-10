from database.db import SessionLocal
from database.db import SessionLocal

from database.raw_models import (
    GerritChange
)

from database.kpi_models import (
    DeveloperSnapshot
)


def save_metric(username, metric_name, metric_value):

    db = SessionLocal()

    db.add(
        DeveloperSnapshot(
            username=username,
            metric_name=metric_name,
            metric_value=float(metric_value)
        )
    )

    db.commit()
    db.close()


def get_developer_metrics(username):

    db = SessionLocal()

    rows = db.query(
        DeveloperSnapshot
    ).filter(
        DeveloperSnapshot.username == username
    ).all()

    db.close()

    return rows

def get_latest_snapshot(username):

    db = SessionLocal()

    snapshot = (
        db.query(DeveloperSnapshot)
        .filter(
            DeveloperSnapshot.username == username
        )
        .order_by(
            DeveloperSnapshot.snapshot_time.desc()
        )
        .first()
    )

    db.close()

    return snapshot

def get_all_developers():

    db = SessionLocal()

    rows = (
        db.query(
            DeveloperSnapshot.username
        )
        .distinct()
        .all()
    )

    db.close()

    return [r[0] for r in rows]

def upsert_gerrit_change(change):

    db = SessionLocal()

    existing = db.get(
        GerritChange,
        change["id"]
    )

    if existing:

        existing.raw_json = change

    else:

        db.add(
            GerritChange(
                change_id=change["id"],
                project=change["project"],
                owner=change["owner"]["username"],
                raw_json=change
            )
        )

    db.commit()
    db.close()

def save_snapshot(
    username,
    metrics
):

    db = SessionLocal()

    db.add(
        DeveloperSnapshot(
            username=username,
            metrics_json=metrics
        )
    )

    db.commit()
    db.close()

def get_all_gerrit_changes():

    db = SessionLocal()

    changes = db.query(GerritChange).all()

    db.close()

    return [c.raw_json for c in changes]