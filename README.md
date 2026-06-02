# EventFlow Backend Engine 🚀

A high-performance, deterministic orchestration engine for hackathons and massive events. Built with Python, FastAPI, and PostgreSQL. 

This backend handles the heavy lifting: ingesting messy CSV data, mathematically balancing teams using O(n²) constraint satisfaction, calculating weighted judging scores, and acting as a strict state machine to prevent unauthorized event advancement.

## 🛠 Tech Stack
* **Framework:** FastAPI (Python 3.10+)
* **Database:** PostgreSQL (via Supabase)
* **ORM:** SQLAlchemy + Pydantic
* **AI/LLM:** Google Gemini API (`google-generativeai`)

---

## 🚀 Getting Started (Local Development)

### 1. Clone & Setup Virtual Environment
```bash
git clone <your-repo-url>
cd eventflow_backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate