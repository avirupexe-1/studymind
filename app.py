import os
import json
import re
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import PyPDF2
import requests as req

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

HF_TOKEN = os.environ.get("HF_TOKEN")

MODEL_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

headers = {}
if HF_TOKEN:
    headers["Authorization"] = f"Bearer {HF_TOKEN}"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(filepath):
    text = ""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)

            for page in reader.pages:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

    except Exception as e:
        return None, str(e)

    return text.strip(), None


def query_llm(prompt, max_tokens=1024):

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": 0.7,
            "return_full_text": False
        }
    }

    try:

        response = req.post(
            MODEL_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 503:
            return None, "Model is loading. Wait 20 seconds and try again."

        result = response.json()

        if isinstance(result, list):
            return result[0]["generated_text"], None

        if "error" in result:
            return None, result["error"]

        return None, str(result)

    except Exception as e:
        return None, str(e)


def truncate_text(text, max_chars=3000):

    if len(text) > max_chars:
        return text[:max_chars] + "...[truncated]"
    return text


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_pdf():

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files allowed'}), 400

    filename = secure_filename(file.filename)

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    file.save(filepath)

    text, error = extract_text_from_pdf(filepath)

    if error:
        return jsonify({'error': error}), 500

    if not text:
        return jsonify({'error': 'PDF contains no readable text'}), 400

    text_filename = filename.rsplit('.', 1)[0] + '.txt'

    text_filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_filename)

    with open(text_filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    return jsonify({
        "success": True,
        "text_file": text_filename,
        "preview": text[:300]
    })


@app.route('/summarize', methods=['POST'])
def summarize():

    data = request.get_json()

    text_file = data.get('text_file')

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)

    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    truncated = truncate_text(text)

    prompt = f"""
Summarize the following document for studying.

Document:
{truncated}
"""

    summary, error = query_llm(prompt, 600)

    if error:
        return jsonify({"error": error}), 500

    return jsonify({"summary": summary.strip()})


@app.route('/quiz', methods=['POST'])
def quiz():

    data = request.get_json()

    text_file = data.get('text_file')

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)

    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    truncated = truncate_text(text, 2500)

    prompt = f"""
Create 5 multiple choice questions based on this document.

Document:
{truncated}
"""

    result, error = query_llm(prompt, 800)

    if error:
        return jsonify({"error": error}), 500

    return jsonify({"quiz": result})


@app.route('/ask', methods=['POST'])
def ask():

    data = request.get_json()

    question = data.get("question")

    text_file = data.get("text_file")

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)

    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    truncated = truncate_text(text, 2500)

    prompt = f"""
Answer the student's question using the document.

Document:
{truncated}

Question:
{question}
"""

    answer, error = query_llm(prompt, 500)

    if error:
        return jsonify({"error": error}), 500

    return jsonify({"answer": answer.strip()})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))

    app.run(host='0.0.0.0', port=port)