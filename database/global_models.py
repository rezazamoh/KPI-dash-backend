from sqlalchemy import Column, Integer, DateTime, JSON
from datetime import datetime

from database.db import Base


class TeamSnapshot(Base):
    __tablename__ = "team_snapshots"

    id = Column(Integer, primary_key=True)

    snapshot_time = Column(
        DateTime,
        default=datetime.utcnow
    )

    metrics_json = Column(JSON)