# Paper Assist MVP

A minimal, **research-ready** web platform to use a fine-tuned ChatGPT-like model to help students revise papers with:
- **Built-in prompt templates**
- **AI interaction & student rating**
- **In-browser editing with versioning**
- **Detailed edit logs (insertions, deletions, replacements)** at word level

> This is an MVP for research. It uses **FastAPI + SQLite** and a simple **vanilla JS** frontend.  
> The AI client is pluggable: set `OPENAI_API_KEY` to use OpenAI, or it will fall back to a dummy suggestion generator.

## Quickstart

### 1) Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# set env (copy .env.example to .env and edit if needed)
cp .env.example .env  # Windows: copy .env.example .env

# run server
uvicorn app:app --reload --port 8000
```

### 2) Frontend
Open `frontend/index.html` directly in a browser **or** serve it with a simple static server.
By default, it points to `http://localhost:8000`.

### 3) Research Data
- All data are stored in `backend/app.db` (SQLite).
- Endpoints are browsable via Swagger: `http://localhost:8000/docs`.

## Notes
- **Prompt templates**: configurable via API or UI.
- **Ratings**: 1–5 stars with optional comment.
- **Diff metrics**: word-level insert/delete/replace counts per revision.
- **Versioning**: each save creates a `Revision` linked to a `Paper` and optionally an `AITurn`.

## Structure
```
paper-assist-mvp/
  backend/
  frontend/
```
