import math
from sqlalchemy.orm import Session
import models

def calculate_variance(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)

def compute_fitness_delta(current_team, candidate, rules):
    """
    Simulates adding the candidate to the team and calculates the new fitness score.
    """
    # Create a simulated team list including the candidate
    simulated_team = current_team + [candidate]
    score = 0.0
    
    # 1. Skill Coverage (40% Weight)
    required_skills = set(rules.get("required_skills", []))
    if required_skills:
        team_skills = set()
        for member in simulated_team:
            # Assuming profile_data has a list of "skills" or a single "primary_skill"
            skills = member.profile_data.get("skills", [])
            if isinstance(skills, str):
                skills = [skills]
            team_skills.update(skills)
            
        covered = required_skills.intersection(team_skills)
        score += (len(covered) / len(required_skills)) * 40

    # 2. Experience Balance (30% Weight)
    # We want low variance (meaning everyone is roughly the same level) OR 
    # high variance (meaning mentorship balance) depending on config. 
    # Defaulting to low variance as per your spec.
    exp_values = [m.profile_data.get("experience_level", 3) for m in simulated_team]
    var = calculate_variance(exp_values)
    score += (1 / (1 + var)) * 30 
    
    # 3. Institution Diversity (20% Weight)
    institutions = [m.profile_data.get("institution", "Unknown") for m in simulated_team]
    unique_institutions = len(set(institutions))
    score += (unique_institutions / len(simulated_team)) * 20
    
    # 4. Configurable Diversity Bonus (10% Weight)
    # E.g., boosting gender diversity if configured by committee
    div_weight = rules.get("diversity_weight", 0)
    if div_weight > 0:
        genders = [m.profile_data.get("gender", "U") for m in simulated_team]
        # Basic example: reward teams with mixed genders
        if len(set(genders)) > 1:
            score += 10 * div_weight
            
    return score

def generate_teams_algorithmically(event_id: int, db: Session):
    # 1. Fetch Event and Rules
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise ValueError("Event not found")
        
    rules = event.configuration.get("rules", {})
    max_size = rules.get("team_size", {}).get("max", 4)
    max_same_inst = rules.get("diversity", {}).get("max_per_institution", 1)

    # 2. Fetch Unassigned Participants
    participants = db.query(models.Participant).filter(
        models.Participant.event_id == event_id,
        models.Participant.team_id == None
    ).all()

    if not participants:
        return []

    # 3. Calculate Skill Rarity & Sort
    skill_counts = {}
    for p in participants:
        skills = p.profile_data.get("skills", [])
        if isinstance(skills, str): skills = [skills]
        for s in skills:
            skill_counts[s] = skill_counts.get(s, 0) + 1

    def rarity_score(participant):
        # Lower count = higher rarity. We sort by rarest first.
        skills = participant.profile_data.get("skills", [])
        if isinstance(skills, str): skills = [skills]
        if not skills: return float('inf')
        return min(skill_counts.get(s, float('inf')) for s in skills)

    participants.sort(key=rarity_score)
    unassigned = list(participants)
    
    # Proposed teams will be a list of lists: [ [p1, p2], [p3, p4] ]
    active_teams = [] 

    # 4. The Greedy Assignment
    for candidate in unassigned:
        best_team_idx = -1
        best_fitness = -1.0
        candidate_inst = candidate.profile_data.get("institution")

        # Evaluate against all currently forming teams
        for idx, team in enumerate(active_teams):
            # HARD CONSTRAINT CHECK: Team Size
            if len(team) >= max_size:
                continue
                
            # HARD CONSTRAINT CHECK: Max Same Institution
            inst_count = sum(1 for m in team if m.profile_data.get("institution") == candidate_inst)
            if inst_count >= max_same_inst:
                continue
                
            # If valid, calculate fitness delta
            fitness = compute_fitness_delta(team, candidate, rules)
            if fitness > best_fitness:
                best_fitness = fitness
                best_team_idx = idx
                
        # Assign to the best valid team, or open a new slot
        if best_team_idx != -1:
            active_teams[best_team_idx].append(candidate)
        else:
            active_teams.append([candidate])

    # 5. Persist to Database (Pending Approval Gate)
    proposed_db_teams = []
    for idx, team_members in enumerate(active_teams):
        new_team = models.Team(
            event_id=event_id,
            name=f"Team {idx + 1}",
            is_approved=0  # MUST be approved before comms go out
        )
        db.add(new_team)
        db.flush() 
        
        for member in team_members:
            member.team_id = new_team.id
            
        proposed_db_teams.append(new_team)

    # 6. Update Event State
    event.state = models.EventState.TEAMS_PROPOSED
    db.commit()
    
    return proposed_db_teams