from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any, Optional

# --- PARTICIPANT SCHEMAS ---
class ParticipantBase(BaseModel):
    name: str
    email: EmailStr
    # profile_data will hold the dynamic traits we use for the algorithm 
    # e.g., {"primary_skill": "Backend", "skill_level": 4, "institution": "IGDTUW"}
    profile_data: Dict[str, Any] = Field(default_factory=dict)

class ParticipantCreate(ParticipantBase):
    pass

class ParticipantResponse(ParticipantBase):
    id: int
    event_id: int
    team_id: Optional[int] = None

    class Config:
        from_attributes = True

# --- EVENT SCHEMAS ---
class EventBase(BaseModel):
    name: str
    configuration: Dict[str, Any] = Field(default_factory=dict)

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    state: str

    class Config:
        from_attributes = True

# --- TEAM SCHEMAS ---
class TeamResponse(BaseModel):
    id: int
    name: str
    rationale: Optional[str] = None
    is_approved: int
    members: List[ParticipantResponse] = []

    class Config:
        from_attributes = True