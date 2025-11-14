from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from . import models, schemas
from .diff_utils import word_diff_counts
from .ai_client import get_suggestion

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Paper Assist MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Prompt Templates ----
@app.post("/api/prompts", response_model=schemas.PromptTemplateOut)
def create_prompt(payload: schemas.PromptTemplateCreate, db: Session = Depends(get_db)):
    p = models.PromptTemplate(title=payload.title, body=payload.body)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@app.get("/api/prompts", response_model=List[schemas.PromptTemplateOut])
def list_prompts(db: Session = Depends(get_db)):
    return db.query(models.PromptTemplate).all()

# ---- Users ----
@app.post("/api/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    u = models.User(name=payload.name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

# ---- Papers ----
@app.post("/api/papers", response_model=schemas.PaperOut)
def create_paper(payload: schemas.PaperCreate, db: Session = Depends(get_db)):
    # basic existence check for user
    user = db.get(models.User, payload.user_id)
    if not user:
        raise HTTPException(404, detail="User not found")
    paper = models.Paper(user_id=payload.user_id, title=payload.title, original_text=payload.original_text)
    db.add(paper)
    db.commit()
    db.refresh(paper)
    # Also create initial revision = original_text for convenience
    rev = models.Revision(paper_id=paper.id, text=paper.original_text, inserted=0, deleted=0, replaced=0)
    db.add(rev)
    db.commit()
    return paper

# ---- AI Suggestion ----
@app.post("/api/ai/suggest", response_model=schemas.AISuggestOut)
async def ai_suggest(payload: schemas.AISuggestIn, db: Session = Depends(get_db)):
    paper = db.get(models.Paper, payload.paper_id)
    if not paper:
        raise HTTPException(404, detail="Paper not found")
    prompt_template = None
    if payload.prompt_template_id:
        pt = db.get(models.PromptTemplate, payload.prompt_template_id)
        if not pt:
            raise HTTPException(404, detail="Prompt template not found")
        prompt_template = pt.body
    suggestion = await get_suggestion(text=payload.text, prompt_template=prompt_template)
    turn = models.AITurn(paper_id=paper.id, prompt_template_id=payload.prompt_template_id, input_text=payload.text, ai_output=suggestion)
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return schemas.AISuggestOut(ai_turn_id=turn.id, suggestion=suggestion)

# ---- Revisions ----
@app.post("/api/revisions", response_model=schemas.RevisionOut)
def create_revision(payload: schemas.RevisionCreate, db: Session = Depends(get_db)):
    paper = db.get(models.Paper, payload.paper_id)
    if not paper:
        raise HTTPException(404, detail="Paper not found")
    # get last revision text
    last_rev = db.query(models.Revision).filter(models.Revision.paper_id==paper.id).order_by(models.Revision.id.desc()).first()
    old_text = last_rev.text if last_rev else paper.original_text
    ins, dele, repl = word_diff_counts(old_text, payload.text)
    rev = models.Revision(paper_id=paper.id, ai_turn_id=payload.ai_turn_id, text=payload.text,
                          inserted=ins, deleted=dele, replaced=repl)
    db.add(rev)
    db.commit()
    db.refresh(rev)
    return rev

# ---- Ratings ----
@app.post("/api/ratings", response_model=schemas.RatingOut)
def create_rating(payload: schemas.RatingCreate, db: Session = Depends(get_db)):
    turn = db.get(models.AITurn, payload.ai_turn_id)
    if not turn:
        raise HTTPException(404, detail="AI turn not found")
    r = models.Rating(ai_turn_id=payload.ai_turn_id, score=payload.score, comment=payload.comment)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

# ---- Stats ----
@app.get("/api/papers/{paper_id}/stats", response_model=schemas.StatsOut)
def paper_stats(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(models.Paper, paper_id)
    if not paper:
        raise HTTPException(404, detail="Paper not found")
    revs = db.query(models.Revision).filter(models.Revision.paper_id==paper_id).all()
    total_inserted = sum(r.inserted for r in revs)
    total_deleted = sum(r.deleted for r in revs)
    total_replaced = sum(r.replaced for r in revs)
    return schemas.StatsOut(paper_id=paper_id, total_inserted=total_inserted, total_deleted=total_deleted,
                            total_replaced=total_replaced, num_revisions=len(revs))
