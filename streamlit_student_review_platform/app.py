import streamlit as st
import json, os, time, uuid, requests
from utils import call_model, parse_model_output, compute_edit_stats, save_student_log, pair_deletes_inserts_as_replacements

st.set_page_config(page_title="PaperFix - Student Paper Review", layout="wide")

CONFIG_PATH = "config.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # default config
    return {
        "models": {
            "model_a": {"name": "fine_tuned_a", "api_url": "", "api_key_env": ""}, 
            "model_b": {"name": "fine_tuned_b", "api_url": "", "api_key_env": ""}
        },
        "tracked_errors": ["A1","B1","C1","D1","F2","I2"],
        "max_upload_mb": 10
    }

config = load_config()

st.title("PaperFix — Streamlit platform for AI-assisted student paper revision")
st.markdown("Students upload papers, AI segments the paper and identifies errors. Students can inspect each error, get personalized explanations and suggestions, edit inline, and resubmit for re-check.")

with st.sidebar:
    st.header("Session")
    student_name = st.text_input("Student name", key="student_name")
    student_id = st.text_input("Student ID", key="student_id")
    st.markdown("---")
    st.header("Config")
    st.write("Edit `config.json` in the project folder to change model endpoints and tracked errors.")
    st.write("Tracked errors:", ", ".join(config.get("tracked_errors", [])))

uploaded = st.file_uploader("Upload your paper (.txt or .md or .pdf supported - txt/md recommended for now)", type=["txt","md"], help="Upload plain text or markdown. PDF parsing is not implemented; please provide text.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "logs" not in st.session_state:
    st.session_state.logs = {"chat": []}

if uploaded:
    raw_bytes = uploaded.read()
    try:
        text = raw_bytes.decode("utf-8")
    except:
        text = raw_bytes.decode("latin-1")
    st.session_state.original_text = text
    st.markdown("### Original text preview")
    st.text_area("Original", value=text, height=250, key="orig_preview")
    if st.button("Submit to AI for segmentation & error detection"):
        with st.spinner("Calling models..."):
            # call primary model (model_a) to segment and identify errors using expected output format
            model_cfg = config["models"]["model_a"]
            resp = call_model(model_cfg, text)
            parsed = parse_model_output(resp)
            st.session_state.ai_segment = parsed.get("segment_data", {})
            st.session_state.ai_errors = parsed.get("error_part", [])
            st.session_state.ai_raw = resp
            # persist initial ai results
            save_student_log(st.session_state.session_id, student_name, student_id, text, "initial", parsed)
            st.success("AI analysis complete. Expand segments and errors below.")

if "ai_segment" in st.session_state:
    st.markdown("## Segmented rhetorical sections")
    for k,v in st.session_state.ai_segment.items():
        with st.expander(k, expanded=False):
            st.write(v)
    st.markdown("## Detected error codes")
    tracked = config.get("tracked_errors", [])
    # create a mapping for error code -> list of spans/occurrences (mock: we don't have per-occurrence data from model output format; assume model will annotate elsewhere; here we'll ask model again to locate occurrences for each error code)
    if st.button("Locate error occurrences and get explanations for each detected error"):
        with st.spinner("Getting detailed error localization and suggestions..."):
            # For each tracked error, ask model to find occurrences and give explanation/suggestion
            error_details = {}
            for code in tracked:
                prompt = f"Given the original text and the model's segmentation, locate every occurrence of writing issue code {code} (if any). For each occurrence, return start_char, end_char, excerpt, personalized explanation why it is an instance of {code}, and a suggested rewrite. Return JSON list or empty list if none."
                model_cfg = config["models"]["model_b"]
                resp = call_model(model_cfg, st.session_state.original_text, extra_system=prompt)
                # assume resp is JSON (or textified JSON)
                try:
                    doc = json.loads(resp)
                except:
                    # if model returns plain text, attempt to parse; here we tolerate flexible outputs
                    doc = {"occurrences": []}
                error_details[code] = doc.get("occurrences", [])
                # log chat
                st.session_state.logs["chat"].append({"time": time.time(), "role":"assistant", "msg": f"Error {code} details fetched."})
            st.session_state.error_details = error_details
            save_student_log(st.session_state.session_id, student_name, student_id, st.session_state.original_text, "error_details", error_details)
            st.success("Error localization complete.")

    if "error_details" in st.session_state:
        st.markdown("## Error review and inline correction")
        edits_summary = {}
        for code, occs in st.session_state.error_details.items():
            with st.expander(f"{code} — {len(occs)} occurrence(s)", expanded=False):
                if len(occs)==0:
                    st.write("No occurrences detected for this code.")
                    continue
                for i,occ in enumerate(occs):
                    st.write(f"**Occurrence {i+1} excerpt:**")
                    excerpt = occ.get("excerpt","")
                    start = occ.get("start_char",0)
                    end = occ.get("end_char",0)
                    st.write(excerpt)
                    st.write("**Personalized explanation:**")
                    st.write(occ.get("explanation","(no explanation returned)"))
                    st.write("**AI suggestion:**")
                    st.write(occ.get("suggestion","(no suggestion returned)"))
                    # Inline editor for the excerpt:
                    key_base = f"{code}_{i}"
                    if key_base + "_timer" not in st.session_state:
                        st.session_state[key_base + "_timer"] = {"start":None, "elapsed":0, "active":False}
                    col1, col2 = st.columns([3,1])
                    with col1:
                        new_text = st.text_area("Edit excerpt", value=excerpt, key=key_base+"_editor", height=120)
                    with col2:
                        if st.session_state[key_base + "_timer"]["active"]:
                            if st.button("Stop timer", key=key_base+"_stop"):
                                st.session_state[key_base + "_timer"]["elapsed"] += time.time() - st.session_state[key_base + "_timer"]["start"]
                                st.session_state[key_base + "_timer"]["active"] = False
                        else:
                            if st.button("Start timer", key=key_base+"_start"):
                                st.session_state[key_base + "_timer"]["start"] = time.time()
                                st.session_state[key_base + "_timer"]["active"] = True
                        st.write("Elapsed (s):", round(st.session_state[key_base + "_timer"]["elapsed"],1))
                        if st.button("Save edit", key=key_base+"_save"):
                            # compute edit stats between excerpt and new_text
                            stats = compute_edit_stats(excerpt, new_text)
                            # pair deletes+inserts as replacements to estimate replaces
                            stats = pair_deletes_inserts_as_replacements(stats)
                            # store
                            if code not in edits_summary:
                                edits_summary[code] = []
                            edits_summary[code].append({
                                "occurrence_index": i,
                                "start_char": start,
                                "end_char": end,
                                "original_excerpt": excerpt,
                                "edited_excerpt": new_text,
                                "edit_stats": stats,
                                "time_spent_s": round(st.session_state[key_base + "_timer"]["elapsed"],1)
                            })
                            st.success("Edit saved for this occurrence.")
                            # update global logs
                            st.session_state.logs["chat"].append({"time": time.time(), "role":"user", "msg": f"Saved edit for {code} occurrence {i}"})
        st.session_state.edits_summary = edits_summary
        save_student_log(st.session_state.session_id, student_name, student_id, st.session_state.original_text, "edits", edits_summary)

        if st.button("Re-check edited excerpts with AI"):
            with st.spinner("Sending edited excerpts to model for verification..."):
                verification = {}
                model_cfg = config["models"]["model_b"]
                for code, edits in st.session_state.edits_summary.items():
                    verification[code] = []
                    for e in edits:
                        prompt = f"Check whether the edited excerpt fixes the issue code {code}. Return JSON {{'fixed': true/false, 'comment': '...' }}."
                        resp = call_model(model_cfg, e["edited_excerpt"], extra_system=prompt)
                        try:
                            v = json.loads(resp)
                        except:
                            v = {"fixed": False, "comment": "Could not parse model output."}
                        verification[code].append(v)
                st.session_state.verification = verification
                save_student_log(st.session_state.session_id, student_name, student_id, st.session_state.original_text, "verification", verification)
                st.success("Verification complete. See results below.")

        if "verification" in st.session_state:
            st.markdown("### Verification results")
            st.write(st.session_state.verification)

        # Download final package
        if st.button("Generate package (zip) for download"):
            package_path = save_student_log(st.session_state.session_id, student_name, student_id, st.session_state.original_text, "final_package", {
                "ai_segment": st.session_state.get("ai_segment"),
                "ai_errors": st.session_state.get("ai_errors"),
                "error_details": st.session_state.get("error_details"),
                "edits_summary": st.session_state.get("edits_summary"),
                "verification": st.session_state.get("verification"),
                "chat_logs": st.session_state.get("logs")
            }, make_zip=True)
            st.success("Package generated.")
            st.markdown(f"[Download the package]({package_path})")

st.markdown("---")
st.caption("Developer notes: modify config.json to set model endpoints and tracked errors. This demo expects the fine-tuned models to follow the `Output Format` JSON described in your prompt. If an API URL isn't set, the app will attempt to use a mock response for local testing.")