// ─────────────────────────────────────────────────────────────
//  StudyMind — script.js
//  All interactivity: upload, tabs, summary, quiz, chat
// ─────────────────────────────────────────────────────────────

// ─── STATE ────────────────────────────────────────────────────
let TF = null;   // path to uploaded text file on server
let QA = 0;      // questions answered
let QC = 0;      // questions correct
let QT = 0;      // questions total

// ─── UPLOAD ───────────────────────────────────────────────────
const DZ = document.getElementById('dropzone');
const FI = document.getElementById('fileInput');

// Drag and drop events
DZ.addEventListener('dragover',  e => { e.preventDefault(); DZ.classList.add('drag-over'); });
DZ.addEventListener('dragleave', () => DZ.classList.remove('drag-over'));
DZ.addEventListener('drop', e => {
  e.preventDefault();
  DZ.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) go(e.dataTransfer.files[0]);
});

// Click to browse
FI.addEventListener('change', e => {
  if (e.target.files[0]) go(e.target.files[0]);
});

// Validate and start upload
function go(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    toast('Please upload a PDF file.', 'err');
    return;
  }
  upload(file);
}

// Send file to Flask /upload route
async function upload(file) {
  DZ.style.opacity = '0.5';
  DZ.style.pointerEvents = 'none';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const response = await fetch('/upload', { method: 'POST', body: fd });
    const data     = await response.json();

    if (data.error) {
      toast(data.error, 'err');
    } else {
      TF = data.text_file;
      document.getElementById('fileName').textContent = file.name;
      document.getElementById('fileMeta').textContent = `${data.word_count.toLocaleString()} words extracted`;
      document.getElementById('fileInfo').classList.add('show');
      document.getElementById('tools').classList.add('show');
      toast('PDF uploaded successfully! ✓', 'ok');
    }
  } catch {
    toast('Upload failed. Is the server running?', 'err');
  }

  DZ.style.opacity = '1';
  DZ.style.pointerEvents = 'auto';
}

// ─── TABS ──────────────────────────────────────────────────────
function switchTab(id, btn) {
  // Remove active state from all tabs and panels
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on'));

  // Activate selected tab and panel
  btn.classList.add('on');
  document.getElementById('panel-' + id).classList.add('on');
}

// ─── SUMMARIZE ────────────────────────────────────────────────
async function doSummary() {
  if (!TF) return;

  const btn = document.getElementById('sumBtn');
  const sp  = document.getElementById('sumSpin');
  const tx  = document.getElementById('sumTxt');
  const out = document.getElementById('sumOut');

  // Show loading state
  btn.disabled = true;
  sp.style.display = 'block';
  tx.textContent = 'Generating…';
  out.innerHTML = '<p class="placeholder">Analyzing your document…</p>';

  try {
    const response = await fetch('/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text_file: TF })
    });
    const data = await response.json();

    if (data.error) {
      out.innerHTML = `<p style="color:rgba(255,155,165,0.95)">${data.error}</p>`;
    } else {
      out.innerHTML = `<div>${md(data.summary)}</div>`;
    }
  } catch {
    out.innerHTML = `<p style="color:rgba(255,155,165,0.95)">Connection failed. Try again.</p>`;
  }

  // Reset button
  btn.disabled = false;
  sp.style.display = 'none';
  tx.textContent = '✦ Regenerate Summary';
}

// ─── QUIZ ──────────────────────────────────────────────────────
async function doQuiz() {
  if (!TF) return;

  const btn  = document.getElementById('qzBtn');
  const sp   = document.getElementById('qzSpin');
  const tx   = document.getElementById('qzTxt');
  const list = document.getElementById('qList');
  const sb   = document.getElementById('scoreBox');

  // Reset state
  btn.disabled = true;
  sp.style.display = 'block';
  tx.textContent = 'Generating…';
  list.innerHTML = '<p class="placeholder">Creating questions…</p>';
  sb.classList.remove('show');
  QA = 0; QC = 0;

  const numQuestions = document.getElementById('numQ').value;

  try {
    const response = await fetch('/quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text_file: TF, num_questions: numQuestions })
    });
    const data = await response.json();

    if (data.error) {
      list.innerHTML = `<p style="color:rgba(255,155,165,0.95)">${data.error}</p>`;
    } else {
      QT = data.questions.length;
      renderQuiz(data.questions);
    }
  } catch {
    list.innerHTML = `<p style="color:rgba(255,155,165,0.95)">Connection failed. Try again.</p>`;
  }

  btn.disabled = false;
  sp.style.display = 'none';
  tx.textContent = '🎯 Regenerate Quiz';
}

// Build quiz question cards in the DOM
function renderQuiz(questions) {
  document.getElementById('qList').innerHTML = questions.map((q, i) => `
    <div class="q-card" id="qc${i}">
      <div class="q-num">Question ${i + 1} of ${questions.length}</div>
      <div class="q-text">${q.question}</div>
      <div class="q-opts">
        ${q.options.map(o => `
          <button class="opt" onclick="pick(this, ${i}, '${esc(o)}', '${esc(q.answer)}')">
            ${o}
          </button>
        `).join('')}
      </div>
      <div class="q-exp" id="qe${i}">${q.explanation || ''}</div>
    </div>
  `).join('');
}

// Handle answer selection
function pick(btn, i, selected, correct) {
  const card = document.getElementById('qc' + i);

  // Prevent re-answering
  if (card.classList.contains('correct') || card.classList.contains('wrong')) return;

  const isCorrect = selected.trim() === correct.trim();

  // Disable all options and highlight correct one
  card.querySelectorAll('.opt').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === correct.trim()) b.classList.add('correct');
  });

  // Mark selected as wrong if incorrect
  if (!isCorrect) btn.classList.add('wrong');

  // Mark card
  card.classList.add(isCorrect ? 'correct' : 'wrong');

  // Show explanation
  const exp = document.getElementById('qe' + i);
  if (exp) exp.classList.add('show');

  // Track score
  QA++;
  if (isCorrect) QC++;

  // Show final score when all answered
  if (QA === QT) {
    document.getElementById('scoreNum').textContent = `${QC}/${QT}`;
    const sb = document.getElementById('scoreBox');
    sb.classList.add('show');
    sb.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ─── CHAT ──────────────────────────────────────────────────────
// Send on Enter key (Shift+Enter for new line)
function ck(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    doAsk();
  }
}

async function doAsk() {
  if (!TF) return;

  const input    = document.getElementById('chatIn');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  addMsg(question, 'user');
  const thinkId = addThinking();

  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text_file: TF, question: question })
    });
    const data = await response.json();
    removeThinking(thinkId);
    addMsg(data.error ? `Error: ${data.error}` : data.answer, 'ai');
  } catch {
    removeThinking(thinkId);
    addMsg('Connection error. Please try again.', 'ai');
  }
}

// Add a message bubble to the chat
function addMsg(text, role) {
  const box = document.getElementById('chatBox');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="av">${role === 'user' ? '🧑' : '🤖'}</div>
    <div class="bbl">${md(text)}</div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

// Add animated thinking dots while waiting
let thinkCount = 0;
function addThinking() {
  const id  = 'think-' + (++thinkCount);
  const box = document.getElementById('chatBox');
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.id = id;
  div.innerHTML = `
    <div class="av">🤖</div>
    <div class="bbl">
      <div class="dots">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return id;
}

function removeThinking(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ─── HELPERS ───────────────────────────────────────────────────

// Convert basic markdown bold/italic to HTML
function md(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/\n/g,            '<br/>');
}

// Escape special chars for use inside onclick attributes
function esc(str) {
  return str
    .replace(/\\/g, '\\\\')
    .replace(/'/g,  "\\'")
    .replace(/"/g,  '&quot;');
}

// ─── TOAST NOTIFICATIONS ───────────────────────────────────────
let toastTimer;
function toast(message, type = 'ok') {
  // Remove existing toast
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  clearTimeout(toastTimer);

  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = message;
  document.body.appendChild(t);

  // Auto-remove after 3.5 seconds
  toastTimer = setTimeout(() => t.remove(), 3500);
}