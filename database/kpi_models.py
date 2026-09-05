from sqlalchemy import Boolean, Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import JSON

from datetime import datetime

from database.db import Base


class DeveloperSnapshot(Base):

    __tablename__ = "developer_snapshots"

    id = Column(
        Integer,
        primary_key=True
    )

    username = Column(
        String,
        index=True
    )

    snapshot_time = Column(
        DateTime,
        default=datetime.now
    )

    metrics_json = Column(JSON)

class TeamSnapshot(Base):

    __tablename__ = "team_snapshots"

    id = Column(
        Integer,
        primary_key=True
    )

    snapshot_time = Column(
        DateTime,
        default=datetime.now
    )

    metrics_json = Column(JSON)


class AppSettings(Base):

    __tablename__ = "app_settings"

    id = Column(
        Integer,
        primary_key=True
    )

    duration_windows = Column(JSON, nullable=True)

    use_duration_windows = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )