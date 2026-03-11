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

<div align="center">

# 📚 StudyMind AI Study Assistant

### The definitive tool for student success

**Upload any PDF → Get AI summaries, quizzes, and instant answers**

[![Live Demo](https://img.shields.io/badge/🚀%20Live%20Demo-Visit%20StudyMind-blueviolet?style=for-the-badge)](https://huggingface.co/spaces/Avirup3121/studymind)
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-orange?style=for-the-badge&logo=huggingface)](https://huggingface.co/spaces/Avirup3121/studymind)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## 🌐 Live Website

> 👉 **[https://huggingface.co/spaces/Avirup3121/studymind](https://huggingface.co/spaces/Avirup3121/studymind)**

No login required. Free to use. Works on desktop and mobile.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 **PDF Upload** | Upload any PDF up to 16 MB — drag & drop or click to browse |
| 📝 **AI Summary** | Instantly get a structured bullet-point summary of your document |
| 🧠 **Quiz Generator** | Auto-generate 3, 5, or 8 multiple-choice questions with answers and explanations |
| 💬 **Ask Anything** | Chat with the AI about your document — ask concepts, definitions, anything |

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.11** | Core programming language |
| **Flask 3.0** | Web framework — handles routes and API endpoints |
| **PyPDF2** | Extracts text content from uploaded PDF files |
| **Gunicorn** | Production WSGI server |
| **Requests** | Makes HTTP calls to the AI inference API |

### Frontend
| Technology | Purpose |
|---|---|
| **HTML5** | Page structure (`templates/index.html`) |
| **CSS3** | All styles with glassmorphism UI (`static/styles.css`) |
| **Vanilla JavaScript** | All interactivity — upload, tabs, quiz logic, chat (`static/script.js`) |
| **Inter (Google Fonts)** | Typography |

### AI Model
| Technology | Purpose |
|---|---|
| **Meta Llama 3.1 8B Instruct** | The large language model powering all AI features |
| **Cerebras (via HF Router)** | Free inference provider — fast, no cold starts |
| **Hugging Face Router API** | Routes requests to the Cerebras inference provider |

### Hosting & Deployment
| Technology | Purpose |
|---|---|
| **Docker** | Containerizes the entire app for consistent deployment |
| **Hugging Face Spaces** | Free cloud hosting platform |
| **Git** | Version control and deployment trigger |

---

## 🔄 How It Works — Full Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│                                                             │
│   1. User uploads PDF                                       │
│   2. User clicks Summarize / Quiz Me / Ask Anything         │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP Request
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND (app.py)                   │
│                                                             │
│   /upload    → PyPDF2 extracts text → saves as .txt file   │
│   /summarize → reads .txt → builds summary prompt           │
│   /quiz      → reads .txt → builds quiz prompt              │
│   /ask       → reads .txt + question → builds Q&A prompt    │
└──────────────────────────┬──────────────────────────────────┘
                           │  POST to HF Router API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              HUGGING FACE ROUTER (Cerebras)                 │
│                                                             │
│   Endpoint: router.huggingface.co/v1/chat/completions      │
│   Model: meta-llama/Llama-3.1-8B-Instruct:cerebras         │
│                                                             │
│   Receives the prompt → runs inference → returns response   │
└──────────────────────────┬──────────────────────────────────┘
                           │  JSON Response
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND (app.py)                   │
│                                                             │
│   Parses the AI response → sends JSON back to browser       │
└──────────────────────────┬──────────────────────────────────┘
                           │  JSON to Frontend
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   BROWSER (script.js)                       │
│                                                             │
│   Renders summary text / quiz cards / chat bubble           │
└─────────────────────────────────────────────────────────────┘
```

