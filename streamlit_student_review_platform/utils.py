import os, json, time, hashlib
import difflib

DATA_ROOT = "student_logs"
os.makedirs(DATA_ROOT, exist_ok=True)

def call_model(model_cfg, text, extra_system=None):
    """
    Call the fine-tuned model via REST API.
    model_cfg: {"name":..., "api_url":..., "api_key_env":...}
    If api_url is empty, returns a mock response useful for local testing.
    """
    if not model_cfg.get("api_url"):
        # return a mocked response following the expected Output Format
        mock = {
            "segment_data": {
                "[Title]": text.split("\\n\\n")[0] if text else "",
                "[claiming centrality]": "",
                "[Describing Real-world Phenomena]": "",
                "[Claiming Importance in the Real World]": "",
                "[Describing Real-world Problem(s)]": "",
                "[Introducing Existing Solution(s)]": "",
                "[Reviewing Previous Research]": "",
                "[Identifying Research Gap(s)]": "",
                "[Showing Mixed Findings]": "",
                "[Articulating Research Purpose(s)]": "",
                "[Method]": "",
                "[Claiming Contribution(s)]": "",
                "[Implication]": ""
            },
            "error_part": []
        }
        return json.dumps(mock, ensure_ascii=False)
    # otherwise, perform HTTP request
    headers = {}
    api_key = None
    if model_cfg.get("api_key_env"):
        import os as _os
        api_key = _os.environ.get(model_cfg["api_key_env"])
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    headers["Content-Type"] = "application/json"
    payload = {"input": text}
    if extra_system:
        payload["system"] = extra_system
    try:
        r = requests.post(model_cfg["api_url"], json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return json.dumps({"error": "request_failed", "detail": str(e)})

def parse_model_output(resp_text):
    """
    Parse the model's output which is expected to be JSON in the provided Output Format.
    """
    try:
        obj = json.loads(resp_text)
    except:
        # attempt to extract json-looking substring
        import re
        m = re.search(r'(\{.*\})', resp_text, re.S)
        if m:
            try:
                obj = json.loads(m.group(1))
            except:
                obj = {}
        else:
            obj = {}
    # ensure keys exist
    return {
        "segment_data": obj.get("segment_data", {}),
        "error_part": obj.get("error_part", [])
    }

def compute_edit_stats(original, edited):
    """
    Compute counts of insertions and deletions at word level using difflib.ndiff.
    Returns dict {"insertions": n, "deletions": m, "replacements": 0}
    Replacement detection is handled by pairing adjacent -/+.
    """
    a = original.split()
    b = edited.split()
    diff = list(difflib.ndiff(a, b))
    insertions = sum(1 for d in diff if d.startswith('+ '))
    deletions = sum(1 for d in diff if d.startswith('- '))
    # naive replacements = 0 for now
    replacements = 0
    return {"insertions": insertions, "deletions": deletions, "replacements": replacements, "raw_diff": diff}

def pair_deletes_inserts_as_replacements(stats):
    """
    Convert adjacent deletion+insertion pairs into replacements to better estimate substitution counts.
    """
    diff = stats.get("raw_diff", [])
    repl = 0
    i = 0
    while i < len(diff)-1:
        if diff[i].startswith('- ') and diff[i+1].startswith('+ '):
            repl += 1
            i += 2
        else:
            i += 1
    # adjust counts
    stats["replacements"] = repl
    stats["deletions"] = max(0, stats["deletions"] - repl)
    stats["insertions"] = max(0, stats["insertions"] - repl)
    return stats

def save_student_log(session_id, student_name, student_id, original_text, tag, payload, make_zip=False):
    """
    Save logs under student_logs/{session_id}/...
    If make_zip True, create a zip package and return a path suitable for Streamlit download link.
    """
    folder = os.path.join(DATA_ROOT, session_id)
    os.makedirs(folder, exist_ok=True)
    # save original if not exists
    with open(os.path.join(folder, "original.txt"), "w", encoding="utf-8") as f:
        f.write(original_text or "")
    # save payload JSON with tag
    filename = f"{tag}.json"
    with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if make_zip:
        zip_path = os.path.join("/mnt/data", f"paper_package_{session_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # add all files in folder
            for fn in os.listdir(folder):
                zf.write(os.path.join(folder, fn), arcname=os.path.join(session_id, fn))
        # return a file:// or relative path that Streamlit can use as link
        return f"/mnt/data/paper_package_{session_id}.zip"
    return os.path.join(folder, filename)