# REALITY.EXE — v0.1

A mobile-first PWA concept for Hacktoberfest 2026 "Touch Grass".

## Core loop
1. Configure a case.
2. Open-source AI generates the mystery.
3. Put the phone away and explore the real world.
4. Photograph evidence.
5. Vision AI verifies it.
6. Solve the case or receive a new clue.

## Run locally
### Backend
```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL on your computer. For phone testing on the same Wi-Fi, run Vite with `npm run dev -- --host` and set `VITE_API_URL` to the computer's LAN URL before starting the frontend.

The backend currently uses Ollama if available and has safe fallback cases for development. Default models are `gemma3:4b` for text and vision; change `TEXT_MODEL` and `VISION_MODEL` environment variables if needed.
