# 🚀 StudyMind — Setup & Deployment Guide

## Project Structure

```
studymind/
├── app.py               ← Flask backend (all API routes)
├── requirements.txt     ← Python dependencies
├── Dockerfile           ← For Hugging Face Spaces deployment
├── README.md            ← Shown on HF Spaces page
├── .gitignore
├── templates/
│   └── index.html       ← Frontend (HTML + CSS + JS)
└── uploads/             ← Temp storage for PDFs (auto-created)
```

---

## Option 1: Run Locally

### Prerequisites
- Python 3.9+
- pip

### Steps

```bash
# 1. Clone or download the project
git clone https://github.com/YOUR_USERNAME/studymind.git
cd studymind

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Set your HuggingFace token for higher rate limits
export HF_TOKEN=hf_your_token_here

# 4. Run the app
python app.py

# 5. Open in browser
# http://localhost:7860
```

---

## Option 2: Deploy to Hugging Face Spaces (FREE)

Hugging Face Spaces provides **free hosting** for ML apps.

### Step 1: Create GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit: StudyMind AI Study Assistant"
git remote add origin https://github.com/YOUR_USERNAME/studymind.git
git push -u origin main
```

### Step 2: Create a Hugging Face Space

1. Go to [huggingface.co](https://huggingface.co) → Sign up (free)
2. Click **"New Space"**
3. Fill in:
   - **Space name**: `studymind` (or any name)
   - **License**: MIT
   - **SDK**: Select **Docker** ⬅️ Important!
   - **Visibility**: Public (so anyone with link can use it)
4. Click **"Create Space"**

### Step 3: Link GitHub to HF Space

In your new Space:
1. Go to **Settings** tab
2. Find **"GitHub repository"** section
3. Connect your GitHub account
4. Select your `studymind` repo
5. Choose `main` branch
6. Click **"Sync"**

HF Spaces will now auto-deploy on every `git push`!

### Step 4: (Optional but Recommended) Add HF Token

Get a **free** API token:
1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click **"New token"** → Name it `studymind` → Role: **Read**
3. Copy the token

Add to Space secrets:
1. In your Space → **Settings** → **Variables and secrets**
2. Click **"New secret"**
3. Name: `HF_TOKEN`, Value: your token
4. Save

Without the token, the app still works but has lower rate limits.

### Step 5: Share!

Your app URL will be:
```
https://huggingface.co/spaces/YOUR_HF_USERNAME/studymind
```

Share this link with anyone — they can use it for **free** with no setup!

---

## Option 3: Manual Docker Deployment

```bash
# Build image
docker build -t studymind .

# Run container
docker run -p 7860:7860 -e HF_TOKEN=your_token studymind

# Visit http://localhost:7860
```

---

## How It Works

```
User uploads PDF
      ↓
Flask extracts text with PyPDF2
      ↓
Text saved to /uploads/ folder
      ↓
User picks: Summarize / Quiz / Ask
      ↓
Flask sends prompt to HuggingFace API
(Mistral-7B-Instruct model — free tier)
      ↓
AI response returned & displayed
```

## AI Model

This app uses **Mistral-7B-Instruct** via HuggingFace's free Inference API.

- **Free**: No credit card, no billing
- **Fast**: Hosted on HF's infrastructure
- **Smart**: Mistral 7B handles summarization, quiz generation, and Q&A well

If you want to swap models, change the `MODEL` variable in `app.py`:
```python
MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
# Other options:
# "HuggingFaceH4/zephyr-7b-beta"
# "meta-llama/Llama-3.2-3B-Instruct" (requires approval)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "AI service error" | HF API rate limit hit — add `HF_TOKEN` |
| PDF shows 0 words | PDF is image-based/scanned — needs OCR |
| Space not building | Check Dockerfile and requirements.txt |
| Slow responses | Free tier has limits — normal behavior |

---

## Contributing

PRs welcome! Some ideas:
- [ ] OCR support for scanned PDFs
- [ ] Export quiz as PDF
- [ ] Highlight source passages for answers
- [ ] Multi-PDF support
- [ ] Save chat history
