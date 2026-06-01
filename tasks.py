import os
import google.generativeai as genai
from sqlalchemy.orm import Session
import models
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API
# Configure the Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 1. Dynamically ask Google what models this specific API key can use
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
print(f"\n--- AI STARTUP: Allowed Models for your API Key: {available_models} ---")

# 2. Auto-select the best available model (Prioritizes 1.5-flash, then 1.0-pro)
target_model = None
for m in available_models:
    if "1.5-flash" in m:
        target_model = m
        break
    elif "1.0-pro" in m:
        target_model = m
        break
    elif "gemini-pro" in m:
        target_model = m
        break

# Ultimate fallback if none of the above match
if not target_model and available_models:
    target_model = available_models[0] 

print(f"--- AI STARTUP: Selected Model: {target_model} ---\n")

generation_config = {
  "temperature": 0.4, 
  "max_output_tokens": 256,
}

# 3. Initialize the model with the guaranteed valid string
model = genai.GenerativeModel(model_name=target_model, generation_config=generation_config)

def generate_team_rationale_background(team_id: int, event_id: int, db: Session):
    """
    Background task to generate an LLM rationale for a specific team.
    """
    # 1. Fetch the team and the event rules
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    
    if not team or not event:
        return
        
    rules = event.configuration.get("rules", {})
    
    # 2. Format the team data for the LLM
    member_descriptions = []
    for member in team.members:
        skills = member.profile_data.get("skills", "Unknown")
        exp = member.profile_data.get("experience_level", "Unknown")
        inst = member.profile_data.get("institution", "Unknown")
        member_descriptions.append(f"- {member.name}: Skills: {skills}, Level: {exp}, College: {inst}")
        
    team_context = "\n".join(member_descriptions)
    
    # 3. The Strict Prompt System
    prompt = f"""
    You are an AI assistant for a hackathon orchestration system.
    The committee has formed a team based on the following rules: {rules}
    
    Here is the team composition:
    {team_context}
    
    Write a concise, 2-sentence rationale explaining why this specific combination of participants is strong, how their skills complement each other, and how they satisfy the rules. 
    Do not use introductory filler (like "Here is the rationale"). Just provide the rationale directly.
    """
    
    # 4. Call Gemini and Save to DB
    try:
        response = model.generate_content(prompt)
        team.rationale = response.text.strip()
        db.commit()
        print(f"Generated rationale for Team {team_id} successfully.")
    except Exception as e:
        print(f"Failed to generate rationale for Team {team_id}: {e}")

def draft_welcome_emails_background(team_id: int, event_id: int, db: Session):
    """
    Background task to draft personalized welcome emails for an approved team.
    """
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    
    if not team or not event:
        return

    # Extract member names and skills
    member_details = ", ".join([
        f"{m.name} ({', '.join(m.profile_data.get('skills', ['Hacker']))})" 
        for m in team.members
    ])
    
    prompt = f"""
    You are the automated communication system for the '{event.name}' event.
    The committee has just approved '{team.name}'. 
    Members: {member_details}.
    Rationale for this grouping: {team.rationale}
    
    Draft a short, energetic welcome email (max 3 paragraphs) to be sent to this team.
    - Welcome them to the event.
    - Briefly mention why they were grouped together (based on the rationale).
    - Tell them their next step is to log into their participant portal.
    Do not include subject lines or placeholder brackets like [Your Name]. Just the email body.
    """
    
    try:
        response = model.generate_content(prompt)
        # For the MVP, we will store the drafted email in the team's rationale column 
        # or a new communications column. Let's append it to the rationale for now so you can see it easily.
        # In a full build, you'd save this to a dedicated CommunicationLog table.
        team.rationale = team.rationale + "\n\n--- DRAFTED EMAIL ---\n" + response.text.strip()
        db.commit()
        print(f"SUCCESS: Drafted welcome email for {team.name}.")
    except Exception as e:
        print(f"ERROR: Failed to draft email for {team.name}: {e}")