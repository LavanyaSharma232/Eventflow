from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import models
from database import engine, get_db
from typing import List
from fastapi import HTTPException
import schemas
import services
import csv
import io
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Body
from pydantic import BaseModel

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EventFlow Orchestration API",
    description="Intelligent Event Orchestration System for Texas Instruments Hackathon",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"status": "System Online", "message": "EventFlow Core is running."}

def verify_team_approval_gate(team_id: int, db: Session = Depends(get_db)):
    """
    SECURITY GATE: Blocks any action targeting a team that lacks committee approval.
    """
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
        
    if team.is_approved == 0:
        raise HTTPException(
            status_code=403, # 403 Forbidden is the correct HTTP code for this
            detail="Security Gate Blocked: This action requires explicit committee approval for the team."
        )
    return team

@app.post("/events/")
def create_event(name: str, db: Session = Depends(get_db)):
    # A dummy configuration for our MVP
    default_config = {
        "rules": {
            "team_size": {"min": 3, "max": 4},
            "diversity": {"max_per_institution": 1}
        },
        "stages": ["intake", "formation", "evaluation", "results"]
    }
    
    new_event = models.Event(name=name, configuration=default_config)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return new_event

@app.post("/events/{event_id}/participants/", response_model=List[schemas.ParticipantResponse])
def upload_participants(event_id: int, participants: List[schemas.ParticipantCreate], db: Session = Depends(get_db)):
    """
    Intake a list of participants for a specific event. 
    This acts as our 'Roster Loaded' stage.
    """
    # 1. Verify the event exists
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 2. Add all participants to the database
    db_participants = []
    for p in participants:
        db_participant = models.Participant(
            event_id=event_id,
            name=p.name,
            email=p.email,
            profile_data=p.profile_data
        )
        db.add(db_participant)
        db_participants.append(db_participant)
    
    # 3. Update the event state
    db_event.state = models.EventState.ROSTER_LOADED
    
    db.commit()
    
    # Refresh to get the generated IDs
    for db_p in db_participants:
        db.refresh(db_p)
        
    return db_participants

@app.post("/events/{event_id}/form-teams/")
def form_teams(event_id: int, db: Session = Depends(get_db)):
    """
    Triggers the deterministic team formation algorithm. (LLM disabled).
    """
    try:
        # Run the strict mathematical sorting
        teams = services.generate_teams_algorithmically(event_id, db)
        return teams 
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/events/{event_id}/approve-teams/")
def approve_teams(event_id: int, db: Session = Depends(get_db)):
    """
    The Human Approval Gate. Locks in the teams and updates event state. (LLM disabled).
    """
    # 1. Verify Event
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    if event.state != models.EventState.TEAMS_PROPOSED:
        raise HTTPException(status_code=400, detail="Teams are not currently pending approval.")

    # 2. Fetch pending teams
    pending_teams = db.query(models.Team).filter(
        models.Team.event_id == event_id,
        models.Team.is_approved == 0
    ).all()

    if not pending_teams:
        raise HTTPException(status_code=400, detail="No pending teams found.")

    # 3. Flip the approval switch and update the state machine
    for team in pending_teams:
        team.is_approved = 1

    event.state = models.EventState.ACTIVE
    db.commit()

    return {
        "status": "success", 
        "message": f"{len(pending_teams)} teams successfully approved.",
        "new_event_state": event.state.value
    }

def verify_team_approval_gate(team_id: int, db: Session = Depends(get_db)):
    """
    SECURITY GATE: Blocks any action targeting a team that lacks committee approval.
    """
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
        
    if team.is_approved == 0:
        raise HTTPException(
            status_code=403, # 403 Forbidden is the correct HTTP code for this
            detail="Security Gate Blocked: This action requires explicit committee approval for the team."
        )
    return team

SKILL_TAXONOMY = {
    "ml": "AI/ML",
    "machine learning": "AI/ML",
    "artificial intelligence": "AI/ML",
    "ai": "AI/ML",
    "backend": "Backend",
    "back-end": "Backend",
    "api": "Backend",
    "frontend": "Frontend",
    "front-end": "Frontend",
    "react": "Frontend",
    "ui": "UI/UX",
    "ux": "UI/UX",
    "design": "UI/UX",
    "data": "Data Science",
    "data science": "Data Science",
}

@app.put("/events/{event_id}/rules/")
def update_event_rules(event_id: int, rules: dict = Body(...), db: Session = Depends(get_db)):
    """
    Receives dynamic rules from the frontend dashboard and updates the JSONB configuration.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    # Merge the new rules into the existing configuration
    current_config = event.configuration or {}
    current_config["rules"] = rules
    
    event.configuration = current_config
    db.commit()
    
    return {"status": "Rules updated successfully", "current_rules": event.configuration["rules"]}

def normalize_skills(raw_skills_str: str) -> list:
    """Takes a messy comma-separated string and returns a clean taxonomy list."""
    if not raw_skills_str:
        return ["General"]
    
    normalized = set()
    raw_list = [s.strip().lower() for s in raw_skills_str.split(',')]
    
    for skill in raw_list:
        # If it matches our dictionary, use the clean version. Otherwise, Title Case it.
        standard_skill = SKILL_TAXONOMY.get(skill, skill.title())
        normalized.add(standard_skill)
        
    return list(normalized)


# --- 2. The CSV Intake Endpoint ---
@app.post("/events/{event_id}/participants/upload/")
async def upload_csv_roster(event_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts a participant roster via CSV upload. Parses, normalizes, and bulk inserts.
    """
    # 1. Verify Event
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Decode the stream safely
    content = await file.read()
    try:
        decoded_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
        
    csv_reader = csv.DictReader(io.StringIO(decoded_content))
    
    # 3. Validate Headers
    required_headers = {"Name", "Email", "Skills"}
    actual_headers = set(csv_reader.fieldnames or [])
    if not required_headers.issubset(actual_headers):
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required CSV headers. Expected at least: {required_headers}"
        )

    # 4. Fetch existing emails for this event to prevent DB crashes
    existing_emails = {
        email[0] for email in db.query(models.Participant.email).filter(models.Participant.event_id == event_id).all()
    }

    participants_to_insert = []
    errors = []
    row_number = 1 # Start at 1 to account for the header row

    # 5. Parse, Validate, and Normalize Row by Row
    for row in csv_reader:
        row_number += 1
        name = row.get("Name", "").strip()
        email = row.get("Email", "").strip()
        
        # A. Graceful Error: Missing critical data
        if not name or not email:
            errors.append(f"Row {row_number}: Missing Name or Email.")
            continue
            
        # B. Graceful Error: Duplicate email
        if email in existing_emails:
            errors.append(f"Row {row_number}: Email '{email}' is already in this event.")
            continue

        # C. Sanitize integer fields
        try:
            experience = int(row.get("Experience", 3))
        except ValueError:
            experience = 3 # Default to 3 if they typed text like "Intermediate"

        # D. Normalize the skills using our taxonomy
        raw_skills = row.get("Skills", "")
        clean_skills = normalize_skills(raw_skills)

        # Build the exact JSONB profile data our Team Algorithm expects
        profile_data = {
            "skills": clean_skills,
            "experience_level": experience,
            "institution": row.get("Institution", "Unknown").strip()
        }
        
        participant = models.Participant(
            event_id=event_id,
            name=name,
            email=email,
            profile_data=profile_data
        )
        participants_to_insert.append(participant)
        
        # Add to local tracking set to catch duplicates within the CSV itself
        existing_emails.add(email) 

    # 6. Bulk Insert to PostgreSQL (Fast)
    if participants_to_insert:
        db.add_all(participants_to_insert)
        
        # Advance the State Machine!
        event.state = models.EventState.ROSTER_LOADED
        db.commit()

    return {
        "status": "success",
        "message": f"Successfully loaded {len(participants_to_insert)} participants.",
        "errors": errors if errors else None
    }

@app.post("/events/{event_id}/evaluations/")
def submit_evaluation(
    event_id: int, 
    team_id: int = Body(...),
    judge_id: str = Body(...),
    scores: dict = Body(...), 
    db: Session = Depends(get_db)
):
    """
    Accepts raw judge scores, calculates the weighted consolidation, 
    and triggers the anomaly detection engine.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 1. Pull dynamic rules from the event configuration
    config = event.configuration or {}
    weights = config.get("scoring_weights", {"technical": 1.0}) 
    anomaly_threshold = config.get("anomaly_threshold", 15.0) # E.g., a 15-point absolute deviation

    # 2. Score Consolidation (Weighted Average)
    # Multiplies the judge's raw score by the configured weight.
    weighted_total = sum(scores.get(category, 0) * weight for category, weight in weights.items())

    # Save the evaluation
    evaluation = models.Evaluation(
        event_id=event_id,
        team_id=team_id,
        judge_id=judge_id,
        scores=scores,
        weighted_total=weighted_total
    )
    db.add(evaluation)
    db.commit()

    # 3. Anomaly Detection Engine
    # Fetch all consolidated scores for this specific team
    team_evals = db.query(models.Evaluation).filter(models.Evaluation.team_id == team_id).all()
    
    # We only run anomaly detection if at least 2 judges have scored the team
    anomalies_flagged = 0
    if len(team_evals) > 1:
        panel_average = sum(e.weighted_total for e in team_evals) / len(team_evals)

        for eval_record in team_evals:
            deviation = abs(eval_record.weighted_total - panel_average)

            # If deviation exceeds threshold, check if it's already been flagged
            if deviation > anomaly_threshold:
                existing_anomaly = db.query(models.ScoreAnomaly).filter(
                    models.ScoreAnomaly.team_id == team_id,
                    models.ScoreAnomaly.judge_id == eval_record.judge_id
                ).first()

                if not existing_anomaly:
                    anomaly = models.ScoreAnomaly(
                        event_id=event_id,
                        team_id=team_id,
                        judge_id=eval_record.judge_id,
                        flagged_score=eval_record.weighted_total,
                        panel_average=panel_average,
                        deviation=deviation
                    )
                    db.add(anomaly)
                    anomalies_flagged += 1
        
        db.commit()

    return {
        "status": "success",
        "judge_id": judge_id,
        "consolidated_score": weighted_total,
        "anomalies_detected_this_run": anomalies_flagged
    }

@app.get("/events/{event_id}/evaluations/anomalies")
def get_score_anomalies(event_id: int, db: Session = Depends(get_db)):
    """Fetches all flagged score deviations for committee review."""
    anomalies = db.query(models.ScoreAnomaly).filter(
        models.ScoreAnomaly.event_id == event_id,
        models.ScoreAnomaly.resolved == 0
    ).all()
    return anomalies

class StageUpdateRequest(BaseModel):
    next_stage: str

@app.patch("/events/{event_id}/stage")
def advance_event_stage(event_id: int, payload: StageUpdateRequest, db: Session = Depends(get_db)):
    """
    Safely transitions the event state by checking strict preconditions first.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    requested_stage = payload.next_stage.upper()

    # PRECONDITION: Cannot move to RESULTS_PENDING if there are unresolved anomalies
    if requested_stage == "RESULTS_PENDING":
        unresolved_anomalies = db.query(models.ScoreAnomaly).filter(
            models.ScoreAnomaly.event_id == event_id,
            models.ScoreAnomaly.resolved == 0
        ).count()
        
        if unresolved_anomalies > 0:
            raise HTTPException(
                status_code=403, 
                detail=f"Cannot advance stage. There are {unresolved_anomalies} unresolved scoring anomalies requiring committee review."
            )

    # PRECONDITION: Cannot move to ACTIVE (Judging) if teams aren't approved
    if requested_stage == "ACTIVE":
        unapproved_teams = db.query(models.Team).filter(
            models.Team.event_id == event_id,
            models.Team.is_approved == 0
        ).count()
        
        if unapproved_teams > 0:
             raise HTTPException(
                status_code=403, 
                detail="Cannot start event. All proposed teams must be approved first."
            )

    # If all checks pass, update the stage
    event.state = requested_stage
    db.commit()

    return {"status": "success", "current_stage": event.state}