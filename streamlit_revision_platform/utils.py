import re, json
from difflib import SequenceMatcher

def extract_text_from_uploaded(uploaded_file):
    # streamlit gives uploaded_file with .getvalue(); user may upload txt or simple text file.
    # For robust PDF/DOCX extraction the user should extend this function (dependencies not included).
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if isinstance(raw, bytes):
        try:
            text = raw.decode('utf-8')
        except:
            try:
                text = raw.decode('latin-1')
            except:
                text = ''
    else:
        text = str(raw)
    # crude fallback: remove extra whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n\s+','\n', text)
    return text

def parse_model_output(output_text):
    """Try to parse model output as JSON. If the model returns additional text, try to extract the JSON blob inside."""
    try:
        return json.loads(output_text)
    except Exception:
        # try to find first { ... } block
        m = re.search(r'(\{.*\})', output_text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except:
                return None
        return None

def word_diff_counts(orig, edited):
    """Return counts of inserted, deleted, replaced words between two strings."""
    a = orig.split()
    b = edited.split()
    sm = SequenceMatcher(None, a, b)
    insertions = deletions = replacements = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'insert':
            insertions += (j2 - j1)
        elif tag == 'delete':
            deletions += (i2 - i1)
        elif tag == 'replace':
            # approximate: min of lengths considered replaced + extra counts
            replacements += max(i2 - i1, j2 - j1)
    return {'insertions': insertions, 'deletions': deletions, 'replacements': replacements}

def count_words(s):
    return len(s.split())
