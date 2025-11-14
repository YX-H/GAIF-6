import os
import httpx
from typing import Optional

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE = os.getenv("API_BASE", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

async def get_suggestion(text: str, prompt_template: Optional[str]) -> str:
    """Return a suggestion string from LLM or a fallback dummy string."""
    prompt = (prompt_template or "You are a concise academic writing assistant.") + "\n\n" + \             "Task: Identify issues and provide concrete, line-edited suggestions.\n" + \             "Student text:\n"""\n" + text + "\n"""\n" + \             "Respond with bullet points and direct rewrite examples."
    if OPENAI_API_KEY:
        try:
            # Using OpenAI Chat Completions format
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "You are an academic writing assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(f"{API_BASE}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"[LLM error fallback] Key set but request failed: {e}.\nMinimal advice: clarify thesis, tighten topic sentences, prefer active voice, and ensure consistent tense."
    # Fallback dummy
    return "- Clarify your thesis in the first paragraph.\n- Merge short sentences to improve cohesion.\n- Replace vague words (e.g., 'things') with precise terms.\n- Example rewrite: 'There are many problems' → 'Two key problems persist: X and Y.'"
