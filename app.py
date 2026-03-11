import os
import json
import time
import requests as req
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import PyPDF2

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

HF_TOKEN  = os.environ.get('HF_TOKEN', None)
MAX_CHARS = 3000
MAX_RETRIES = 3
RETRY_DELAY = 6

# ── CORRECT endpoint: router.huggingface.co/v1 ────────────────────────────
# Model format: "model-id:provider"  — cerebras is free via HF token
API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL   = "meta-llama/Llama-3.1-8B-Instruct:cerebras"
  
  

# ─── CORE AI CALLER ────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set. Add it in your Space → Settings → Variables and secrets.")

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    last_error = "Unknown error"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = req.post(API_URL, headers=headers, json=payload, timeout=60)

            # 503 — still loading
            if response.status_code == 503:
                last_error = "Service unavailable (503)."
                print(f"[{attempt}/{MAX_RETRIES}] 503 – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Empty body
            if not response.text or not response.text.strip():
                last_error = "Empty response body."
                print(f"[{attempt}/{MAX_RETRIES}] Empty – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Auth errors
            if response.status_code in (401, 403):
                raise RuntimeError("Authentication failed. Check your HF_TOKEN in Space secrets.")

            # Other errors
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                time.sleep(RETRY_DELAY)
                continue

            # Parse
            try:
                data = response.json()
            except ValueError:
                last_error = f"JSON parse error: {response.text[:200]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                time.sleep(RETRY_DELAY)
                continue

            text = (
                data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
            )

            if not text:
                last_error = "Empty content in response."
                print(f"[{attempt}/{MAX_RETRIES}] {last_error} – retrying…")
                time.sleep(RETRY_DELAY)
                continue

            return text  # ✅

        except req.exceptions.Timeout:
            last_error = "Request timed out."
            print(f"[{attempt}/{MAX_RETRIES}] Timeout – retrying…")
            time.sleep(RETRY_DELAY)

        except req.exceptions.RequestException as e:
            last_error = str(e)
            print(f"[{attempt}/{MAX_RETRIES}] Error: {e}")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"AI unavailable after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


# ─── HELPERS ───────────────────────────────────────────────────────────────

def read_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── ROUTES ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    filename = secure_filename(file.filename)
    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
    txt_path = pdf_path.replace('.pdf', '.txt')
    file.save(pdf_path)

    try:
        reader = PyPDF2.PdfReader(pdf_path)
        text   = '\n'.join(page.extract_text() or '' for page in reader.pages).strip()
    except Exception as e:
        return jsonify({'error': f'Could not read PDF: {str(e)}'}), 500

    if not text:
        return jsonify({'error': 'No readable text found in this PDF'}), 400

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return jsonify({'text_file': txt_path, 'word_count': len(text.split())})


@app.route('/summarize', methods=['POST'])
def summarize():
    data     = request.json or {}
    txt_path = data.get('text_file')
    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'File not found — please re-upload your PDF.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    system = "You are a helpful study assistant. Summarize documents clearly and concisely."
    user   = f"Summarize the following text using bullet points for key ideas:\n\n{text}"

    try:
        return jsonify({'summary': call_llm(system, user, max_tokens=400)})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


@app.route('/quiz', methods=['POST'])
def quiz():
    data     = request.json or {}
    txt_path = data.get('text_file')
    num_q    = int(data.get('num_questions', 5))
    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'File not found — please re-upload your PDF.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    system = "You are a quiz generator. You only output valid JSON arrays with no extra text, no markdown."
    user   = (
        f"Create {num_q} multiple-choice questions from the text below.\n"
        "Output ONLY a JSON array, nothing else:\n"
        '[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],'
        '"answer":"A. ...","explanation":"..."}]\n\n'
        f"Text:\n{text}"
    )

    try:
        raw = call_llm(system, user, max_tokens=1000)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    # Strip markdown fences if present
    clean = raw.strip()
    if '```' in clean:
        parts = clean.split('```')
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith('json'):
            clean = clean[4:]
        clean = clean.strip()

    start = clean.find('[')
    end   = clean.rfind(']')
    if start != -1 and end != -1:
        clean = clean[start:end+1]

    try:
        return jsonify({'questions': json.loads(clean)})
    except json.JSONDecodeError:
        return jsonify({'error': 'Could not parse quiz — try regenerating.', 'raw': raw[:300]}), 500


@app.route('/ask', methods=['POST'])
def ask():
    data     = request.json or {}
    txt_path = data.get('text_file')
    question = data.get('question', '').strip()
    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'File not found — please re-upload your PDF.'}), 400
    if not question:
        return jsonify({'error': 'No question provided.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    system = "You are a helpful study assistant. Answer questions using only the provided document. Be clear and concise."
    user   = f"Document:\n{text}\n\nQuestion: {question}"

    try:
        return jsonify({'answer': call_llm(system, user, max_tokens=350)})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860)