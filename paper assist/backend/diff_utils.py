import re
from difflib import SequenceMatcher
from typing import Tuple

WORD_RE = re.compile(r"\w+|[^\w\s]|")  # tokenize words and punctuation

def tokenize(text: str):
    return WORD_RE.findall(text)

def word_diff_counts(old: str, new: str) -> Tuple[int, int, int]:
    """Return (inserted, deleted, replaced) counts at token level."""
    a = tokenize(old)
    b = tokenize(new)
    sm = SequenceMatcher(a=a, b=b)
    inserted = deleted = replaced = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'insert':
            inserted += (j2 - j1)
        elif tag == 'delete':
            deleted += (i2 - i1)
        elif tag == 'replace':
            len_a = i2 - i1
            len_b = j2 - j1
            # Count substitutions as min overlap, remainder as ins/del
            common = min(len_a, len_b)
            replaced += common
            if len_b > len_a:
                inserted += (len_b - len_a)
            elif len_a > len_b:
                deleted += (len_a - len_b)
        # 'equal' does not contribute
    return inserted, deleted, replaced
