# SmritiNER - SIH26003
Runnable Python/FastAPI hackathon MVP for AI-assisted cognitive gaming and memory assistance.

## Run
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
Open http://127.0.0.1:8000

Demo: patient/1234 and caregiver/1234
SQLite database is created automatically. No external AI API is required.
The adaptive engine uses recent accuracy + response time to adjust difficulty.
Voice uses browser Web Speech API where supported.
This is a game-performance prototype, not a medical diagnosis/treatment tool.
