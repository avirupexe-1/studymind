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

HF_TOKEN    = os.environ.get('HF_TOKEN', None)
API_URL     = "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.3"
MAX_CHARS   = 3000   # max PDF text sent to model
MAX_RETRIES = 4      # retry attempts on empty / 503 responses
RETRY_DELAY = 8      # seconds to wait between retries


# ─── CORE AI CALLER ────────────────────────────────────────────────────────

def call_mistral(prompt: str, max_new_tokens: int = 512) -> str:
    """
    Call Mistral-7B with automatic retry on:
      - empty body          (model cold-starting on HF free tier)
      - HTTP 503            (model still loading)
      - JSON decode errors  (partial / malformed response)
    Returns the generated text string.
    Raises RuntimeError with a user-friendly message on total failure.
    """
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": 0.7,
            "do_sample": True,
            "return_full_text": False,
        }
    }
    headers = {"Content-Type": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    last_error = "Unknown error"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = req.post(API_URL, headers=headers, json=payload, timeout=90)

            # 503 — model is still warming up
            if response.status_code == 503:
                last_error = "Model is loading (HTTP 503)."
                print(f"[{attempt}/{MAX_RETRIES}] 503 – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Empty body — cold start returns nothing
            if not response.text or not response.text.strip():
                last_error = "Empty response body (model cold-starting)."
                print(f"[{attempt}/{MAX_RETRIES}] Empty body – retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
                continue

            # Non-200 with body
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                if response.status_code in (401, 403):
                    break   # no point retrying auth errors
                time.sleep(RETRY_DELAY)
                continue

            # Parse JSON
            try:
                data = response.json()
            except ValueError:
                last_error = f"JSON decode error. Raw: {response.text[:200]}"
                print(f"[{attempt}/{MAX_RETRIES}] {last_error}")
                time.sleep(RETRY_DELAY)
                continue

            # Extract generated text
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "").strip()
            elif isinstance(data, dict):
                text = data.get("generated_text", "").strip()
            else:
                text = ""

            if not text:
                last_error = "Model returned empty generated_text."
                print(f"[{attempt}/{MAX_RETRIES}] {last_error} – retrying…")
                time.sleep(RETRY_DELAY)
                continue

            return text  # ✅ success

        except req.exceptions.Timeout:
            last_error = "Request timed out after 90s."
            print(f"[{attempt}/{MAX_RETRIES}] Timeout – retrying…")
            time.sleep(RETRY_DELAY)

        except req.exceptions.RequestException as e:
            last_error = str(e)
            print(f"[{attempt}/{MAX_RETRIES}] Request error: {e}")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(
        f"The AI model is currently loading on Hugging Face's servers. "
        f"Please wait 20–30 seconds and try again. (Last error: {last_error})"
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
        return jsonify({'error': 'Text file not found — please re-upload your PDF.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    prompt = (
        "[INST] You are a helpful study assistant. "
        "Summarize the following text in a clear, structured way. "
        "Use bullet points for key ideas and keep it concise.\n\n"
        f"{text} [/INST]"
    )

    try:
        result = call_mistral(prompt, max_new_tokens=400)
        return jsonify({'summary': result})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


@app.route('/quiz', methods=['POST'])
def quiz():
    data     = request.json or {}
    txt_path = data.get('text_file')
    num_q    = int(data.get('num_questions', 5))

    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'Text file not found — please re-upload your PDF.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    prompt = (
        f"[INST] Create {num_q} multiple-choice questions from the text below. "
        "Respond ONLY with a valid JSON array, no extra text, no markdown fences.\n\n"
        "Each item:\n"
        '{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],'
        '"answer":"A. ...","explanation":"..."}\n\n'
        f"Text:\n{text} [/INST]"
    )

    try:
        raw = call_mistral(prompt, max_new_tokens=900)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

    # Clean markdown fences if model added them
    clean = raw.strip()
    if clean.startswith('```'):
        parts = clean.split('```')
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith('json'):
            clean = clean[4:]
        clean = clean.strip()

    # Find JSON array bounds
    start = clean.find('[')
    end   = clean.rfind(']')
    if start != -1 and end != -1:
        clean = clean[start:end+1]

    try:
        questions = json.loads(clean)
        return jsonify({'questions': questions})
    except json.JSONDecodeError:
        return jsonify({
            'error': 'Could not parse quiz — try regenerating.',
            'raw': raw[:300]
        }), 500


@app.route('/ask', methods=['POST'])
def ask():
    data     = request.json or {}
    txt_path = data.get('text_file')
    question = data.get('question', '').strip()

    if not txt_path or not os.path.exists(txt_path):
        return jsonify({'error': 'Text file not found — please re-upload your PDF.'}), 400
    if not question:
        return jsonify({'error': 'No question provided.'}), 400

    text   = read_text(txt_path)[:MAX_CHARS]
    prompt = (
        "[INST] You are a helpful study assistant. "
        "Answer the question below using ONLY the provided document. "
        "Be clear, concise and accurate.\n\n"
        f"Document:\n{text}\n\n"
        f"Question: {question} [/INST]"
    )

    try:
        answer = call_mistral(prompt, max_new_tokens=350)
        return jsonify({'answer': answer})
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860)