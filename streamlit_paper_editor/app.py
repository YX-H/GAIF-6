
import streamlit as st
import requests, json, time, os, difflib
from io import StringIO, BytesIO
from zipfile import ZipFile
from datetime import datetime
import tempfile

# ---- Helpers ----
def load_preset(path="model_configs.json"):
    try:
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

def load_errors(path="errors.json"):
    try:
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

def read_uploaded_file(uploaded):
    if uploaded is None:
        return ""
    name = uploaded.name.lower()
    data = uploaded.getvalue()
    if name.endswith(".txt"):
        return data.decode("utf-8")
    elif name.endswith(".pdf"):
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(BytesIO(data))
            text = []
            for p in reader.pages:
                text.append(p.extract_text() or "")
            return "\n\n".join(text)
        except Exception as e:
            return ""
    elif name.endswith(".docx"):
        try:
            import docx
            from io import BytesIO
            doc = docx.Document(BytesIO(data))
            return "\n\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            return ""
    else:
        # fallback
        try:
            return data.decode("utf-8")
        except:
            return ""

def call_model(cfg, payload, timeout=40):
    """
    cfg: dict with keys: url, api_key_env (optional), headers (optional)
    payload: dict to POST as json
    returns dict or text
    """
    try:
        headers = {"Content-Type":"application/json"}
        # prefer environment var if provided
        api_key = None
        if isinstance(cfg, dict):
            api_key_env = cfg.get("api_key_env")
            if api_key_env:
                api_key = os.environ.get(api_key_env)
            # allow explicit api_key in config (not recommended)
            if not api_key and cfg.get("api_key"):
                api_key = cfg.get("api_key")
            # optionally allow extra headers
            extra = cfg.get("headers", {})
            headers.update(extra)
        if api_key:
            # common pattern: Authorization: Bearer <key>
            headers.setdefault("Authorization", f"Bearer {api_key}")
        url = cfg.get("url")
        if not url:
            return {"error":"model URL not configured in model_configs.json"}
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        try:
            return r.json()
        except:
            return {"text": r.text, "status_code": r.status_code}
    except Exception as e:
        return {"error": str(e)}

def compute_word_diff_stats(original, edited):
    # compare at word level
    a = original.split()
    b = edited.split()
    sm = difflib.SequenceMatcher(None, a, b)
    inserts = deletes = replaces = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            inserts += (j2 - j1)
        elif tag == "delete":
            deletes += (i2 - i1)
        elif tag == "replace":
            # consider replace as max of lengths changed
            replaces += max(i2 - i1, j2 - j1)
    return {"insertions": inserts, "deletions": deletes, "replacements": replaces}

def ensure_session():
    if "original_text" not in st.session_state:
        st.session_state.original_text = ""
    if "current_text" not in st.session_state:
        st.session_state.current_text = ""
    if "segments" not in st.session_state:
        st.session_state.segments = {}
    if "errors_detected" not in st.session_state:
        st.session_state.errors_detected = {}  # {code: {"present":bool, "instances":[{snippet,start,end}], "ai_check":{...}}}
    if "edit_logs" not in st.session_state:
        st.session_state.edit_logs = []  # list of edits
    if "ai_chat_log" not in st.session_state:
        st.session_state.ai_chat_log = []  # list of {"time","model","role","payload","response"}
    if "timers" not in st.session_state:
        st.session_state.timers = {}  # start times keyed by a unique edit id

# ---- UI ----
st.set_page_config(page_title="论文写作AI辅导平台 (Streamlit)", layout="wide")
st.title("论文写作AI辅导平台（Streamlit）")
st.markdown("将论文提交到微调模型，逐步发现并修改写作错误。包括计时与修改统计。")

ensure_session()

with st.sidebar:
    st.header("运行/配置")
    st.markdown("请在 `model_configs.json` 中配置两个模型：`segment_model` 和 `error_model`。可通过环境变量提供 API key（参见模板）。")
    if st.button("加载预设配置"):
        st.experimental_rerun()
    st.markdown("**预设错误定义 (errors.json)**")
    if st.button("打开 errors.json (在项目目录中编辑并重新加载)"):
        st.experimental_rerun()

col1, col2 = st.columns([1,2])
with col1:
    name = st.text_input("学生姓名", value="")
    stu_id = st.text_input("学号", value="")
    uploaded = st.file_uploader("上传论文（支持 txt, pdf, docx）", type=["txt","pdf","docx"])
    if uploaded:
        text = read_uploaded_file(uploaded)
        if st.button("确认并加载论文文本"):
            st.session_state.original_text = text
            st.session_state.current_text = text
            st.session_state.segments = {}
            st.session_state.errors_detected = {}
            st.session_state.edit_logs = []
            st.session_state.ai_chat_log = []
            st.experimental_rerun()
    st.markdown("---")
    st.markdown("**模型/预设文件**")
    st.markdown("在项目目录中修改 `model_configs.json` 和 `errors.json` 后重新点击加载应用。")
    if st.button("重新加载全部页面"):
        st.experimental_rerun()

with col2:
    st.subheader("论文预览 / 当前文本")
    st.text_area("当前论文全文（学生可在此整体编辑，但建议通过每项错误的编辑界面逐条修改以获得差异统计）",
                 value=st.session_state.current_text, height=300, key="main_textarea")
    # keep current_text synced
    st.session_state.current_text = st.session_state.main_textarea

# --- Model interaction controls
st.markdown("---")
cfg = load_preset("model_configs.json")
errors_def = load_errors("errors.json")
st.sidebar.markdown("**已加载模型配置**")
st.sidebar.json(cfg)

col_a, col_b, col_c = st.columns(3)
with col_a:
    if st.button("发送至分段模型 (segment_model)"):
        if not cfg.get("segment_model"):
            st.error("请在 model_configs.json 配置 segment_model")
        else:
            payload = {"text": st.session_state.current_text, "instruction":"Return JSON with key 'segment_data' following the Output Format."}
            st.info("请求已发送，等待模型返回...")
            resp = call_model(cfg["segment_model"], payload)
            st.session_state.ai_chat_log.append({"time":datetime.utcnow().isoformat()+"Z","model":"segment_model","request":payload,"response":resp})
            if isinstance(resp, dict):
                st.session_state.segments = resp.get("segment_data", {})
                st.success("分段结果已保存。")
            else:
                st.error("模型返回格式异常。")
            st.experimental_rerun()
with col_b:
    if st.button("发送至错误检测模型 (error_model)"):
        if not cfg.get("error_model"):
            st.error("请在 model_configs.json 配置 error_model")
        else:
            payload = {"text": st.session_state.current_text, "instruction":"Identify which error codes among the configured ones appear in the text. Return JSON with keys: 'error_part' (list of codes), and optionally 'instances' mapping code -> list of {'snippet':..., 'start':int,'end':int}."}
            st.info("请求已发送，等待模型返回...")
            resp = call_model(cfg["error_model"], payload)
            st.session_state.ai_chat_log.append({"time":datetime.utcnow().isoformat()+"Z","model":"error_model","request":payload,"response":resp})
            if isinstance(resp, dict):
                codes = resp.get("error_part", [])
                instances = resp.get("instances", {})
                # build detected structure
                detected = {}
                for code in errors_def.keys():
                    detected[code] = {"present": code in codes, "instances": instances.get(code, [])}
                st.session_state.errors_detected = detected
                st.success("错误检测结果已保存。")
            else:
                st.error("模型返回格式异常。")
            st.experimental_rerun()
with col_c:
    if st.button("清空检测/会话记录"):
        st.session_state.segments = {}
        st.session_state.errors_detected = {}
        st.session_state.edit_logs = []
        st.session_state.ai_chat_log = []
        st.success("已清空。")
        st.experimental_rerun()

# Display segments
if st.session_state.segments:
    st.markdown("### AI 分段结果")
    for k,v in st.session_state.segments.items():
        with st.expander(k, expanded=False):
            st.write(v)

# Display errors and editing UI
st.markdown("### 错误检测与编辑")
if not errors_def:
    st.info("未找到 errors.json，请在项目目录中添加并定义错误代码（示例文件已包含）。")
else:
    for code, meta in errors_def.items():
        det = st.session_state.errors_detected.get(code, {"present":False, "instances":[]})
        header = f"{code} — {meta.get('name','')}"
        with st.expander(header, expanded=False):
            st.write(meta.get("description",""))
            st.write("模型判断：" + ("出现该错误" if det.get("present") else "未出现该错误"))
            instances = det.get("instances", [])
            if instances:
                st.write(f"检测到 {len(instances)} 处实例：")
                for idx, inst in enumerate(instances):
                    snippet = inst.get("snippet", "")
                    start = inst.get("start")
                    end = inst.get("end")
                    st.markdown(f"**实例 {idx+1}:**")
                    st.code(snippet)
                    col1, col2, col3 = st.columns([1,1,1])
                    edit_id = f"{code}__{idx}"
                    if st.button("开始编辑此实例", key=f"start_edit_{edit_id}"):
                        # open editor by setting session state
                        st.session_state.timers[edit_id] = time.time()
                        st.session_state["_editing"] = {"code":code,"idx":idx,"orig_snippet":snippet,"start":start,"end":end}
                        st.experimental_rerun()
                    if st.button("放弃编辑此实例", key=f"giveup_{edit_id}"):
                        # record give up
                        start_t = st.session_state.timers.pop(edit_id, None)
                        duration = (time.time()-start_t) if start_t else None
                        st.session_state.edit_logs.append({
                            "time": datetime.utcnow().isoformat()+"Z",
                            "code": code,
                            "idx": idx,
                            "action":"give_up",
                            "duration_seconds": duration,
                            "orig_snippet": snippet,
                            "edited_snippet": None,
                            "diff": None
                        })
                        st.success("放弃记录已保存。")
                        st.experimental_rerun()
            else:
                st.write("该模型未提供具体实例位置，或未检测到此错误。")
            # If user is editing this instance show editor
            editing = st.session_state.get("_editing")
            if editing and editing.get("code")==code:
                idx = editing.get("idx")
                orig = editing.get("orig_snippet")
                st.markdown("#### 编辑器（仅编辑该实例文本）")
                st.write("编辑器启动时间已记录。")
                edited = st.text_area("修改为（请在此编辑）", value=orig, key=f"editarea_{code}_{idx}")
                colx, coly = st.columns(2)
                with colx:
                    if st.button("提交修改", key=f"submit_edit_{code}_{idx}"):
                        edit_id = f"{code}__{idx}"
                        start_t = st.session_state.timers.pop(edit_id, None)
                        duration = (time.time()-start_t) if start_t else None
                        diff = compute_word_diff_stats(orig, edited)
                        # persist edit: replace in current_text if possible via snippet match
                        replaced = False
                        ct = st.session_state.current_text
                        if orig and orig in ct:
                            ct = ct.replace(orig, edited, 1)
                            st.session_state.current_text = ct
                            replaced = True
                        st.session_state.edit_logs.append({
                            "time": datetime.utcnow().isoformat()+"Z",
                            "code": code,
                            "idx": idx,
                            "action":"submit",
                            "duration_seconds": duration,
                            "orig_snippet": orig,
                            "edited_snippet": edited,
                            "diff": diff,
                            "replaced_in_fulltext": replaced
                        })
                        # remove editing flag
                        st.session_state.pop("_editing", None)
                        st.success("修改已保存并应用到全文（如找到原文）。")
                        st.experimental_rerun()
                with coly:
                    if st.button("取消编辑（放弃）", key=f"cancel_edit_{code}_{idx}"):
                        edit_id = f"{code}__{idx}"
                        start_t = st.session_state.timers.pop(edit_id, None)
                        duration = (time.time()-start_t) if start_t else None
                        st.session_state.edit_logs.append({
                            "time": datetime.utcnow().isoformat()+"Z",
                            "code": code,
                            "idx": idx,
                            "action":"cancel",
                            "duration_seconds": duration,
                            "orig_snippet": orig,
                            "edited_snippet": None,
                            "diff": None
                        })
                        st.session_state.pop("_editing", None)
                        st.success("已取消并记录。")
                        st.experimental_rerun()

# Summary of edits and download
st.markdown("---")
st.subheader("修改记录与导出")
st.write(f"已记录 {len(st.session_state.edit_logs)} 次编辑操作。")
if st.session_state.edit_logs:
    st.json(st.session_state.edit_logs)
# Button to create ZIP of session artifacts
def create_export_zip():
    base = tempfile.mkdtemp()
    # original text
    orig_path = os.path.join(base,"original_version.txt")
    with open(orig_path,"w",encoding="utf-8") as f:
        f.write(st.session_state.original_text)
    # current text
    curr_path = os.path.join(base,"final_version.txt")
    with open(curr_path,"w",encoding="utf-8") as f:
        f.write(st.session_state.current_text)
    # segments
    seg_path = os.path.join(base,"ai_segments.json")
    with open(seg_path,"w",encoding="utf-8") as f:
        json.dump(st.session_state.segments, f, ensure_ascii=False, indent=2)
    # errors detected (raw model outputs stored in ai_chat_log)
    errors_path = os.path.join(base,"ai_error_detection.json")
    # extract related entries from ai_chat_log
    with open(errors_path,"w",encoding="utf-8") as f:
        # store last known error detection response and full chat log
        json.dump({
            "errors_detected": st.session_state.errors_detected,
            "ai_chat_log": st.session_state.ai_chat_log
        }, f, ensure_ascii=False, indent=2)
    # edit logs
    edits_path = os.path.join(base,"edit_logs.json")
    with open(edits_path,"w",encoding="utf-8") as f:
        json.dump(st.session_state.edit_logs, f, ensure_ascii=False, indent=2)
    # write a README
    readme_path = os.path.join(base,"README_session.txt")
    with open(readme_path,"w",encoding="utf-8") as f:
        f.write("This export contains:\n- original_version.txt\n- final_version.txt\n- ai_segments.json\n- ai_error_detection.json\n- edit_logs.json\n\nGenerated at: " + datetime.utcnow().isoformat()+"Z\n")
    # create zip
    zip_bytes = BytesIO()
    with ZipFile(zip_bytes, "w") as z:
        for fname in [orig_path, curr_path, seg_path, errors_path, edits_path, readme_path]:
            z.write(fname, arcname=os.path.basename(fname))
    zip_bytes.seek(0)
    return zip_bytes

if st.button("导出当前会话为压缩包 (.zip)"):
    zipb = create_export_zip()
    st.download_button("点击下载会话压缩包", data=zipb, file_name=f"session_export_{int(time.time())}.zip", mime="application/zip")

st.markdown("----")
st.markdown("**说明**：\n- 请在 `model_configs.json` 配置你的微调模型 API 地址与 API key 的环境变量名。\n- 程序演示了：分段、错误检测、逐条实例编辑、计时、差异统计与会话导出。\n- 若错误检测模型未提供实例位置，本平台将仅记录错误代码；你可以在全文中手动定位并复制到编辑器进行修改。\n")
