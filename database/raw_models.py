from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import JSON

from database.db import Base


class GerritChange(Base):

    __tablename__ = "gerrit_changes"

    change_id = Column(
        String,
        primary_key=True
    )

    project = Column(String)

    owner = Column(String)

    updated_at = Column(DateTime)

    raw_json = Column(JSON)