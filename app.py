import os
import json
import re
import requests as req
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import PyPDF2

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}
HF_TOKEN = os.environ.get('HF_TOKEN', None)
API_URL = "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.3"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath):
    text = ""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        return None, str(e)
    return text.strip(), None

def query_llm(prompt, max_tokens=1024):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": 0.7,
            "return_full_text": False
        }
    }
    try:
        response = req.post(API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 503:
            return None, "Model is loading, please wait 20 seconds and try again."
        if not response.text:
            return None, "Empty response. Model may be loading. Try again in 20 seconds."
        result = response.json()
        if isinstance(result, list):
            return result[0]["generated_text"], None
        if isinstance(result, dict) and "error" in result:
            return None, result["error"]
        return None, f"Unexpected response: {str(result)}"
    except Exception as e:
        return None, str(e)

def truncate_text(text, max_chars=3000):
    if len(text) > max_chars:
        return text[:max_chars] + "...[truncated for brevity]"
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
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    text, error = extract_text_from_pdf(filepath)
    if error:
        return jsonify({'error': f'Failed to extract text: {error}'}), 500
    if not text:
        return jsonify({'error': 'No text found in PDF. It may be scanned/image-based.'}), 400
    text_filename = filename.rsplit('.', 1)[0] + '.txt'
    text_filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_filename)
    with open(text_filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    word_count = len(text.split())
    return jsonify({
        'success': True,
        'filename': filename,
        'text_file': text_filename,
        'word_count': word_count,
        'preview': text[:300] + '...' if len(text) > 300 else text
    })

@app.route('/summarize', methods=['POST'])
def summarize():
    data = request.get_json()
    text_file = data.get('text_file')
    if not text_file:
        return jsonify({'error': 'No text file specified'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found. Please re-upload your PDF.'}), 404
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    truncated = truncate_text(text, 3000)
    prompt = f"""<s>[INST] You are an expert academic assistant. Summarize the following document clearly and concisely.
Structure your summary with:
1. **Main Topic** - What this document is about
2. **Key Points** - The 4-6 most important concepts or arguments
3. **Conclusion** - The main takeaway

Document:
{truncated}
[/INST]"""
    summary, error = query_llm(prompt, max_tokens=600)
    if error:
        return jsonify({'error': f'AI service error: {error}'}), 500
    return jsonify({'summary': summary.strip()})

@app.route('/quiz', methods=['POST'])
def generate_quiz():
    data = request.get_json()
    text_file = data.get('text_file')
    num_questions = min(int(data.get('num_questions', 5)), 8)
    if not text_file:
        return jsonify({'error': 'No text file specified'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found. Please re-upload your PDF.'}), 404
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    truncated = truncate_text(text, 2500)
    prompt = f"""<s>[INST] You are a quiz generator. Based on the document below, create exactly {num_questions} multiple choice questions.

Return ONLY a valid JSON array. No explanation, no markdown, just the JSON.
Format:
[
  {{
    "question": "Question text here?",
    "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
    "answer": "A) option1",
    "explanation": "Brief explanation why this is correct."
  }}
]

Document:
{truncated}
[/INST]"""
    result, error = query_llm(prompt, max_tokens=1200)
    if error:
        return jsonify({'error': f'AI service error: {error}'}), 500
    try:
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            questions = json.loads(result.strip())
        return jsonify({'questions': questions})
    except json.JSONDecodeError:
        return jsonify({'error': 'Could not parse quiz format. Try again.', 'raw': result}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    text_file = data.get('text_file')
    question = data.get('question', '').strip()
    if not text_file or not question:
        return jsonify({'error': 'Missing text file or question'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], text_file)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found. Please re-upload your PDF.'}), 404
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    truncated = truncate_text(text, 2500)
    prompt = f"""<s>[INST] You are a helpful study assistant. Answer the student's question based ONLY on the provided document.
Be clear, accurate, and educational. If the answer isn't in the document, say so honestly.

Document:
{truncated}

Student's Question: {question}
[/INST]"""
    answer, error = query_llm(prompt, max_tokens=512)
    if error:
        return jsonify({'error': f'AI service error: {error}'}), 500
    return jsonify({'answer': answer.strip()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=False)