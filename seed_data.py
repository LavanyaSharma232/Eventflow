import requests

BASE_URL = "http://127.0.0.1:8000"

print("--- Starting EventFlow Data Seed ---")

# 1. Create the Event
print("1. Creating Event...")
event_res = requests.post(f"{BASE_URL}/events/?name=TI+Coding+Contest")
event_id = event_res.json().get("id")
print(f"   -> Event created with ID: {event_id}")

# 2. Load the Roster
print("2. Loading Roster...")
roster = [
  {"name": "Lavanya Sharma", "email": f"lavanya{event_id}@gmail.com", "profile_data": {"primary_skill": "Backend", "skill_level": 5, "institution": "IGDTUW"}},
  {"name": "Alex Chen", "email": f"alex{event_id}@example.com", "profile_data": {"primary_skill": "Frontend", "skill_level": 4, "institution": "University B"}},
  {"name": "Sam Taylor", "email": f"sam{event_id}@example.com", "profile_data": {"primary_skill": "UI/UX", "skill_level": 4, "institution": "University C"}},
  {"name": "Jordan Lee", "email": f"jordan{event_id}@example.com", "profile_data": {"primary_skill": "Backend", "skill_level": 3, "institution": "IGDTUW"}},
  {"name": "Casey Smith", "email": f"casey{event_id}@example.com", "profile_data": {"primary_skill": "Frontend", "skill_level": 5, "institution": "University B"}}
]

roster_res = requests.post(f"{BASE_URL}/events/{event_id}/participants/", json=roster)
print(f"   -> Roster loaded! Status Code: {roster_res.status_code}")

if roster_res.status_code == 200:
    print("SUCCESS! Data is officially in PostgreSQL.")
else:
    # Use .text instead of .json() so the script doesn't crash if FastAPI returns a raw 500 HTML error
    print(f"Error: {roster_res.text}")