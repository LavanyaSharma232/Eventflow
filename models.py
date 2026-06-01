from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text, Float, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

class EventState(enum.Enum):
    SETUP = "setup"
    ROSTER_LOADED = "roster_loaded"
    TEAMS_PROPOSED = "teams_proposed"
    ACTIVE = "active"
    RESULTS_PENDING = "results_pending"
    COMPLETED = "completed"

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    state = Column(Enum(EventState), default=EventState.SETUP)
    
    # THE SECRET WEAPON: This stores the rules, stages, and LLM prompts as a JSON object
    configuration = Column(JSONB, nullable=False, default={}) 
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    participants = relationship("Participant", back_populates="event")
    teams = relationship("Team", back_populates="event")

class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    
    # Store their skills, institution, and experience level dynamically
    profile_data = Column(JSONB, nullable=False, default={})
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    
    event = relationship("Event", back_populates="participants")
    team = relationship("Team", back_populates="members")

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String, nullable=False)
    
    # The Gemini-generated explanation of why this team was formed
    rationale = Column(Text, nullable=True) 
    
    # Has the committee approved this team?
    is_approved = Column(Integer, default=0) # 0 = Pending, 1 = Approved
    
    event = relationship("Event", back_populates="teams")
    members = relationship("Participant", back_populates="team")

# Add to models.py

class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    judge_id = Column(String, index=True) # We use String here so we can pass names like "Judge Smith"
    scores = Column(JSON) # Stores the raw breakdown: {"technical": 80, "pitch": 90}
    weighted_total = Column(Float) # The consolidated math result

class ScoreAnomaly(Base):
    __tablename__ = "score_anomalies"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    judge_id = Column(String)
    flagged_score = Column(Float)
    panel_average = Column(Float)
    deviation = Column(Float)
    resolved = Column(Integer, default=0) # 0 = Pending, 1 = Resolved