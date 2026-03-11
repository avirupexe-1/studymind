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
RETRY_DELAY = 8

# ── NEW API: Chat Completions endpoint (works as of 2025) ──────────────────
# Uses meta-llama/Meta-Llama-3.1-8B-Instruct via HF router — free with HF token
API_URL = "https://router.huggingface.co/novita/v1/chat/completions"
MODEL   = "meta-llama/Meta-Llama-3.1-8B-Instruct"


# ─── CORE AI CALLER ────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
    """
    Call LLM via HF Router chat completions API.
    Retries on 503 / empty responses (cold start).
    """
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set. Add it in your Space secrets.")

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
            response = req.post(API_URL, headers=headers, json=payload, timeout=90)

            # 503 — model loading
            if response.status_code == 503:
                last_error = "Service unavailable (503)."
                print(f"[{attempt}/{MAX_RETRIES}] 503 – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Empty body
            if not response.text or not response.text.strip():
                last_error = "Empty response body."
                print(f"[{attempt}/{MAX_RETRIES}] Empty body – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Auth errors — no point retrying
            if response.status_code in (401, 403):
                raise RuntimeError(
                    "Authentication failed. Check your HF_TOKEN in Space secrets."
                )

            # Other non-200
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                time.sleep(RETRY_DELAY)
                continue

            # Parse response
            try:
                data = response.json()
            except ValueError:
                last_error = f"JSON decode error: {response.text[:200]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                time.sleep(RETRY_DELAY)
                continue

            # Extract content from chat completions format
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            if not text:
                last_error = "Empty content in response."
                print(f"[{attempt}/{MAX_RETRIES}] {last_error} – retrying…")
                time.sleep(RETRY_DELAY)
                continue

            return text  # ✅ success

        except req.exceptions.Timeout:
            last_error = "Request timed out."
            print(f"[{attempt}/{MAX_RETRIES}] Timeout – retrying…")
            time.sleep(RETRY_DELAY)

        except req.exceptions.RequestException as e:
            last_error = str(e)
            print(f"[{attempt}/{MAX_RETRIES}] Request error: {e}")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"AI service unavailable after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}. Please try again in 30 seconds."
    )


# ─── HELPERS ───────────────────────────────────────────────────────────────

def read_text(path: str) -> str:
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

    text = read_text(txt_path)[:MAX_CHARS]

    system = "You are a helpful study assistant. Summarize documents clearly and concisely."
    user   = f"Summarize the following text using bullet points for key ideas:\n\n{text}"

    try:
        result = call_llm(system, user, max_tokens=400)
        return jsonify({'summary': result})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


@app.route('/quiz', methods=['POST'])
def quiz():
    data     = request.json or {}
    txt_path = data.get('text_file')
    num_q    = int(data.get('num_questions', 5))

    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'File not found — please re-upload your PDF.'}), 400

    text = read_text(txt_path)[:MAX_CHARS]

    system = "You are a quiz generator. You only respond with valid JSON arrays, no extra text."
    user   = (
        f"Create {num_q} multiple-choice questions from the text below.\n"
        "Respond ONLY with a JSON array in this exact format, nothing else:\n"
        '[{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],'
        '"answer":"A. ...","explanation":"..."}]\n\n'
        f"Text:\n{text}"
    )

    try:
        raw = call_llm(system, user, max_tokens=1000)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    # Clean markdown fences
    clean = raw.strip()
    if '```' in clean:
        parts = clean.split('```')
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith('json'):
            clean = clean[4:]
        clean = clean.strip()

    # Find JSON array
    start = clean.find('[')
    end   = clean.rfind(']')
    if start != -1 and end != -1:
        clean = clean[start:end+1]

    try:
        questions = json.loads(clean)
        return jsonify({'questions': questions})
    except json.JSONDecodeError:
        return jsonify({
            'error': 'Could not parse quiz format — try regenerating.',
            'raw': raw[:300]
        }), 500


@app.route('/ask', methods=['POST'])
def ask():
    data     = request.json or {}
    txt_path = data.get('text_file')
    question = data.get('question', '').strip()

    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'File not found — please re-upload your PDF.'}), 400
    if not question:
        return jsonify({'error': 'No question provided.'}), 400

    text = read_text(txt_path)[:MAX_CHARS]

    system = "You are a helpful study assistant. Answer questions using only the provided document text. Be clear and concise."
    user   = f"Document:\n{text}\n\nQuestion: {question}"

    try:
        answer = call_llm(system, user, max_tokens=350)
        return jsonify({'answer': answer})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860)