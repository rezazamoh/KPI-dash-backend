from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import DateTime
from sqlalchemy import JSON

from database.db import Base

class GerritChange(Base):

    __tablename__ = "gerrit_changes"

    change_id = Column(
        String,
        primary_key=True
    )

    change_number = Column(Integer, index=True)

    project = Column(String)

    owner = Column(String, index=True)

    status = Column(String)

    created_at = Column(DateTime)

    updated_at = Column(DateTime, index=True)

    raw_json = Column(JSON)

class JiraIssue(Base):
    __tablename__ = "jira_issues"

    issue_id = Column(String, primary_key=True)
    issue_key = Column(String, unique=True, nullable=False, index=True)

    project = Column(String, index=True)
    summary = Column(String)
    status = Column(String)
    issue_type = Column(String)
    assignee = Column(String)
    priority = Column(String)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    resolved_at = Column(DateTime)

    raw_json = Column(JSON)