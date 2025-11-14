import streamlit as st
import os, json, time, requests, zipfile
from utils import extract_text_from_uploaded, parse_model_output, word_diff_counts
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title='Paper Revision Assistant', layout='wide')

BASE_DIR = Path(__file__).parent
CONFIG = json.loads(open(BASE_DIR / 'config.json','r',encoding='utf-8').read())
PRESETS = json.loads(open(BASE_DIR / 'presets.json','r',encoding='utf-8').read())
ERROR_CODES = PRESETS.get('error_codes', [])
LABELS = PRESETS.get('labels', {})

if 'session_id' not in st.session_state:
    st.session_state['session_id'] = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
if 'log' not in st.session_state:
    st.session_state['log'] = {'events':[]}

st.title('Paper Revision Platform (Streamlit)')
st.write('Fill name & student ID, upload a paper, and use the AI-assisted revision workflow.')

with st.sidebar:
    st.header('Student info')
    name = st.text_input('Student name', value='')
    sid = st.text_input('Student ID', value='')
    st.markdown('---')
    st.header('Model config')
    st.text('API URL:')
    api_url = st.text_input('API URL', value=CONFIG.get('api_url',''))
    api_key_env = st.text_input('API key env var name', value=CONFIG.get('api_key_env','MODEL_API_KEY'))
    timeout_seconds = st.number_input('Timeout seconds', value=CONFIG.get('timeout_seconds',60), min_value=5)

uploaded = st.file_uploader('Upload paper (txt recommended)', type=['txt','md','pdf','docx'], accept_multiple_files=False)

if uploaded:
    text = extract_text_from_uploaded(uploaded)
    st.session_state['original_text'] = text
    st.success('Uploaded. Extracted approx. %d words.' % len(text.split()))
else:
    text = st.session_state.get('original_text','')

col1, col2 = st.columns([3,1])
with col1:
    st.subheader('Paper (editable)')
    edited_text = st.text_area('Editable paper text', value=text, height=400, key='editable_text')
with col2:
    st.subheader('Controls')
    if st.button('Send to model for segmentation & error detection'):
        if not api_url:
            st.error('Please set API URL in sidebar.')
        else:
            # call model
            payload = {
                'prompt': PRESETS.get('model_prompts',{}).get('segmentation_prompt',''),
                'input_text': edited_text,
                'allowed_error_codes': ERROR_CODES
            }
            headers = {}
            api_key = os.getenv(api_key_env)
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            try:
                r = requests.post(api_url, json=payload, headers=headers, timeout=timeout_seconds)
                r.raise_for_status()
                model_output = r.text
            except Exception as e:
                st.error('Model call failed: ' + str(e))
                model_output = ''
            parsed = parse_model_output(model_output)
            if parsed is None:
                st.error('Failed to parse model output as JSON. Raw output saved to session.')
                st.session_state['last_raw_model_output'] = model_output
            else:
                st.session_state['model_result'] = parsed
                st.success('Model returned results.')
                st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'model_call','payload':parsed})
    st.markdown('---')
    st.write('Presets (editable in presets.json):')
    st.write(ERROR_CODES)
    st.write([LABELS.get(c,c) for c in ERROR_CODES])

# If we have model_result, show segmentation and errors
model_result = st.session_state.get('model_result')
if model_result:
    st.subheader('Segmentation (from model)')
    st.json(model_result.get('segment_data',{}))
    st.subheader('Detected error codes')
    error_part = model_result.get('error_part',[])
    # ensure only preset codes shown
    error_part = [c for c in error_part if c in ERROR_CODES]
    st.write('Detected codes:', error_part)
    # For each possible error code, create expandable item
    for code in ERROR_CODES:
        label = LABELS.get(code, code)
        detected = code in error_part
        with st.expander(f'{code} — {label} ' + ('(detected)' if detected else '(not detected)')):
            cols = st.columns([4,1,1])
            span_text = st.text_area(f'Example problematic span for {code}', value='', key=f'span_{code}', height=80)
            start_button = cols[1].button('Start edit', key=f'start_{code}')
            done_button = cols[2].button('Mark done', key=f'done_{code}')
            # timer logic
            if start_button:
                st.session_state.setdefault('timers',{})[code] = time.time()
                st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'timer_start','code':code})
            if done_button:
                t0 = st.session_state.setdefault('timers',{}).pop(code, None)
                if t0:
                    elapsed = time.time() - t0
                else:
                    elapsed = None
                st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'timer_end','code':code,'elapsed':elapsed})
                st.success(f'Completed editing {code}. Time used: {elapsed:.1f}s' if elapsed else 'Marked done.')
            # When user asks for explanation and suggestion, call model_explanation
            if st.button('Get AI explanation & suggestion for this span', key=f'explain_{code}'):
                api_url_local = api_url or CONFIG.get('api_url')
                if not api_url_local:
                    st.error('Set API URL in sidebar.')
                else:
                    payload = {
                        'prompt': PRESETS.get('model_prompts',{}).get('error_explanation_prompt',''),
                        'code': code,
                        'span': span_text,
                        'full_text': st.session_state.get('original_text','')
                    }
                    headers = {}
                    api_key = os.getenv(api_key_env)
                    if api_key:
                        headers['Authorization'] = f'Bearer {api_key}'
                    try:
                        r = requests.post(api_url_local, json=payload, headers=headers, timeout=timeout_seconds)
                        r.raise_for_status()
                        out = r.text
                    except Exception as e:
                        st.error('Model call failed: ' + str(e))
                        out = ''
                    parsed = None
                    try:
                        parsed = json.loads(out)
                    except:
                        # try to extract JSON
                        import re
                        m = re.search(r'(\{.*\})', out, flags=re.DOTALL)
                        if m:
                            try:
                                parsed = json.loads(m.group(1))
                            except:
                                parsed = None
                    if parsed:
                        st.json(parsed)
                        st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'explain','code':code,'response':parsed})
                    else:
                        st.error('Failed to parse AI response; saved raw.')
                        st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'explain_raw','code':code,'raw':out})
            # Provide editing box and track diffs
            new_span = st.text_area(f'Edit span for {code}', value=span_text, key=f'edit_{code}', height=120)
            if st.button('Submit edit for check', key=f'submit_edit_{code}'):
                # compute diff counts and log
                counts = word_diff_counts(span_text or '', new_span or '')
                st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'submit_edit','code':code,'counts':counts,'orig':span_text,'edited':new_span})
                # re-run model on edited span for re-check (lightweight)
                api_url_local = api_url or CONFIG.get('api_url')
                if api_url_local:
                    payload = {'prompt': PRESETS.get('model_prompts',{}).get('error_explanation_prompt',''),
                               'code': code, 'span': new_span, 'full_text': st.session_state.get('original_text','')}
                    headers = {}
                    api_key = os.getenv(api_key_env)
                    if api_key:
                        headers['Authorization'] = f'Bearer {api_key}'
                    try:
                        r = requests.post(api_url_local, json=payload, headers=headers, timeout=timeout_seconds)
                        r.raise_for_status()
                        out = r.text
                    except Exception as e:
                        st.error('Model call failed: ' + str(e))
                        out = ''
                    parsed = None
                    try:
                        parsed = json.loads(out)
                    except:
                        pass
                    if parsed and parsed.get('code') == code:
                        # naive success detection: if reason indicates resolved, user can decide
                        st.success('AI checked the edited span; see AI feedback below.')
                        st.json(parsed)
                        st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'recheck','code':code,'response':parsed})
                    else:
                        st.info('AI returned response but could not be parsed as JSON with code field; raw saved.')
                        st.session_state['log']['events'].append({'time':datetime.utcnow().isoformat(),'type':'recheck_raw','code':code,'raw':out})
# End per-error loop

st.markdown('---')
st.header('Session controls & download')
if st.button('Save session log'):
    # saves session log and other artifacts
    outdir = BASE_DIR / 'outputs' / st.session_state['session_id']
    outdir.mkdir(parents=True, exist_ok=True)
    # write original and final text
    (outdir / 'original.txt').write_text(st.session_state.get('original_text',''), encoding='utf-8')
    (outdir / 'final.txt').write_text(st.session_state.get('editable_text',''), encoding='utf-8')
    # write model_result and log
    (outdir / 'model_result.json').write_text(json.dumps(st.session_state.get('model_result',{}), indent=2, ensure_ascii=False), encoding='utf-8')
    (outdir / 'session_log.json').write_text(json.dumps(st.session_state.get('log',{}), indent=2, ensure_ascii=False), encoding='utf-8')
    st.success(f'Saved to {outdir}')
if st.button('Download results (zip)'):
    outdir = BASE_DIR / 'outputs' / st.session_state['session_id']
    if not outdir.exists():
        st.error('No saved outputs yet — press "Save session log" first.')
    else:
        zip_path = BASE_DIR / f'results_{st.session_id}.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in outdir.rglob('*'):
                zf.write(p, arcname=str(p.relative_to(outdir)))
        with open(zip_path, 'rb') as f:
            data = f.read()
        st.download_button('Click to download zip', data=data, file_name=zip_path.name)
        st.success('Downloaded.')

st.markdown('---')
st.caption('Preset files: edit presets.json and config.json to customize error codes, labels, and model prompts.')
