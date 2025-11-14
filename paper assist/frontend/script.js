const $ = (id) => document.getElementById(id);
const state = {
  apiBase: "http://localhost:8000",
  userId: null,
  paperId: null,
  lastAITurnId: null,
};

$('apiBase').addEventListener('change', e => state.apiBase = e.target.value);

async function api(path, opts={}) {
  const res = await fetch(`${state.apiBase}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function seed() {
  try {
    const promptBodies = [
      { title: 'Grammar & Mechanics', body: 'Focus on grammar, punctuation, and sentence clarity. Provide minimal pairs and rewrites.' },
      { title: 'Coherence & Cohesion', body: 'Focus on transitions, topic sentences, and paragraph flow. Provide structural suggestions.' },
      { title: 'Academic Style', body: 'Ensure formal tone, hedging where needed, and discipline-appropriate vocabulary.' }
    ];
    for (const p of promptBodies) await api('/api/prompts', { method: 'POST', body: JSON.stringify(p) });
    const u = await api('/api/users', { method: 'POST', body: JSON.stringify({ name: 'Student A' }) });
    state.userId = u.id;
    $('seedStatus').textContent = 'Seeded 3 prompts and 1 user ✓';
    await loadPrompts();
  } catch (e) {
    $('seedStatus').textContent = 'Seed error: ' + e.message;
  }
}

async function loadPrompts() {
  const prompts = await api('/api/prompts');
  const sel = $('promptSelect');
  sel.innerHTML = '';
  const opt = document.createElement('option');
  opt.value = '';
  opt.textContent = '(no template)';
  sel.appendChild(opt);
  prompts.forEach(p => {
    const o = document.createElement('option');
    o.value = p.id;
    o.textContent = `${p.id}: ${p.title}`;
    sel.appendChild(o);
  });
}

$('seed').addEventListener('click', seed);

$('createPaper').addEventListener('click', async () => {
  try {
    const name = $('userName').value.trim() || 'Student';
    if (!state.userId) {
      const u = await api('/api/users', { method: 'POST', body: JSON.stringify({ name }) });
      state.userId = u.id;
    }
    const title = $('paperTitle').value.trim() || 'Untitled Paper';
    const original_text = $('paperText').value.trim();
    const p = await api('/api/papers', { method: 'POST', body: JSON.stringify({ user_id: state.userId, title, original_text }) });
    state.paperId = p.id;
    $('paperInfo').textContent = `Paper #${p.id} created for user #${state.userId}`;
    $('reviseText').value = original_text;
    await loadPrompts();
  } catch (e) {
    $('paperInfo').textContent = 'Error: ' + e.message;
  }
});

$('getSuggestion').addEventListener('click', async () => {
  if (!state.paperId) { alert('Create a paper first.'); return; }
  try {
    const promptId = $('promptSelect').value || null;
    const text = $('aiInput').value.trim() || $('reviseText').value.trim();
    const out = await api('/api/ai/suggest', { method: 'POST', body: JSON.stringify({ paper_id: state.paperId, prompt_template_id: promptId ? Number(promptId) : null, text }) });
    state.lastAITurnId = out.ai_turn_id;
    $('aiSuggestion').textContent = out.suggestion;
    $('ratingPanel').classList.remove('hidden');
    $('ratingStatus').textContent = '';
  } catch (e) {
    $('aiSuggestion').textContent = 'Error: ' + e.message;
  }
});

$('submitRating').addEventListener('click', async () => {
  if (!state.lastAITurnId) { alert('Ask AI first.'); return; }
  try {
    const score = Number($('ratingScore').value);
    const comment = $('ratingComment').value;
    const out = await api('/api/ratings', { method: 'POST', body: JSON.stringify({ ai_turn_id: state.lastAITurnId, score, comment }) });
    $('ratingStatus').textContent = 'Thanks! Saved ✓';
  } catch (e) {
    $('ratingStatus').textContent = 'Error: ' + e.message;
  }
});

$('saveRevision').addEventListener('click', async () => {
  if (!state.paperId) { alert('Create a paper first.'); return; }
  try {
    const text = $('reviseText').value.trim();
    const ai_turn_id = state.lastAITurnId || null;
    const out = await api('/api/revisions', { method: 'POST', body: JSON.stringify({ paper_id: state.paperId, ai_turn_id, text }) });
    $('reviseStatus').textContent = `Saved revision #${out.id}. (+${out.inserted}/-${out.deleted}/~${out.replaced})`;
  } catch (e) {
    $('reviseStatus').textContent = 'Error: ' + e.message;
  }
});

$('loadStats').addEventListener('click', async () => {
  if (!state.paperId) { alert('Create a paper first.'); return; }
  try {
    const s = await api(`/api/papers/${state.paperId}/stats`);
    $('stats').textContent = JSON.stringify(s, null, 2);
  } catch (e) {
    $('stats').textContent = 'Error: ' + e.message;
  }
});

// init
loadPrompts().catch(()=>{});
