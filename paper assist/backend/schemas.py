from pydantic import BaseModel, Field
from typing import Optional, List

class PromptTemplateCreate(BaseModel):
    title: str
    body: str

class PromptTemplateOut(BaseModel):
    id: int
    title: str
    body: str
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    name: str

class UserOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class PaperCreate(BaseModel):
    user_id: int
    title: str
    original_text: str

class PaperOut(BaseModel):
    id: int
    user_id: int
    title: str
    original_text: str
    class Config:
        from_attributes = True

class AISuggestIn(BaseModel):
    paper_id: int
    prompt_template_id: Optional[int] = None
    text: str

class AISuggestOut(BaseModel):
    ai_turn_id: int
    suggestion: str

class RevisionCreate(BaseModel):
    paper_id: int
    ai_turn_id: Optional[int] = None
    text: str

class RevisionOut(BaseModel):
    id: int
    paper_id: int
    ai_turn_id: Optional[int]
    text: str
    inserted: int
    deleted: int
    replaced: int
    class Config:
        from_attributes = True

class RatingCreate(BaseModel):
    ai_turn_id: int
    score: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class RatingOut(BaseModel):
    id: int
    ai_turn_id: int
    score: int
    comment: Optional[str]
    class Config:
        from_attributes = True

class StatsOut(BaseModel):
    paper_id: int
    total_inserted: int
    total_deleted: int
    total_replaced: int
    num_revisions: int
