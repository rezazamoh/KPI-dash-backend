from sqlalchemy import DateTime
from sqlalchemy import JSON
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base
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

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

    members = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    projects = relationship(
        "TeamDefaultProject",
        back_populates="team",
        cascade="all, delete-orphan",
    )

class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)

    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    username = Column(String, nullable=False)

    team = relationship(
        "Team",
        back_populates="members",
    )

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "username",
            name="uq_team_member",
        ),
    )

class Dev(Base):
    __tablename__ = "gerrit_developers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)

class Project(Base):
    __tablename__ = "gerrit_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    
class TeamDefaultProject(Base):
    __tablename__ = "team_default_projects"

    id = Column(Integer, primary_key=True, index=True)

    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    project_id = Column(
        Integer,
        ForeignKey("gerrit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    team = relationship("Team", back_populates="projects")
    project = relationship("Project")

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "project_id",
            name="uq_team_default_project",
        ),
    )