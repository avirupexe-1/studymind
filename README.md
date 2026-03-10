---
title: StudyMind AI Study Assistant
emoji: 📚
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# 📚 StudyMind — AI Study Assistant

An AI-powered study tool that helps you learn from any PDF document.

## Features
- 📝 **Summarize** — Get a structured summary of any PDF
- 🧠 **Quiz Generator** — Auto-generate multiple choice questions
- 💬 **Ask Anything** — Chat with your document using AI

## Tech Stack
- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python + Flask
- **AI**: Mistral-7B via Hugging Face Inference API
- **Deployment**: Hugging Face Spaces (Docker)

## Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/studymind
cd studymind
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:7860`

## Hugging Face Spaces Setup

1. Fork this repo or push to your GitHub
2. Go to [huggingface.co/spaces](https://huggingface.co/spaces) → New Space
3. Choose **Docker** as the SDK
4. Link your GitHub repo
5. Add your `HF_TOKEN` as a Space secret (optional, for higher rate limits)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `HF_TOKEN` | HuggingFace API token for higher limits | Optional |

Get a free token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
