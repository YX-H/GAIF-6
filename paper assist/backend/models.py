from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)  # e.g., 'You are an academic writing assistant...'

class Paper(Base):
    __tablename__ = "papers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    original_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")
    revisions = relationship("Revision", back_populates="paper")

class AITurn(Base):
    __tablename__ = "ai_turns"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=True)
    input_text = Column(Text, nullable=False)
    ai_output = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Revision(Base):
    __tablename__ = "revisions"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    ai_turn_id = Column(Integer, ForeignKey("ai_turns.id"), nullable=True)  # optional link to suggestion used
    text = Column(Text, nullable=False)
    inserted = Column(Integer, default=0)
    deleted = Column(Integer, default=0)
    replaced = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    paper = relationship("Paper", back_populates="revisions")

class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True, index=True)
    ai_turn_id = Column(Integer, ForeignKey("ai_turns.id"), nullable=False)
    score = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
