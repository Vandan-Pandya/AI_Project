# XAI — Explain. Understand. Analyze.

Dark-themed Explainable AI assistant with FastAPI backend (Google Gemini, OpenAI, Groq, OpenRouter, DeepSeek, Ollama, or mock mode).

## Quick Start (One Server)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Set your API key in .env or configure live in the UI Settings modal:
# GEMINI_API_KEY=your_key_here
# GEMINI_MODEL=gemini-1.5-flash

# 3. Start the server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## Features

- **Google Gemini & Multi-Provider Support**: Direct async integration with Google Gemini (`gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash`, `gemini-2.5-flash`) as well as OpenAI, Groq, OpenRouter, DeepSeek, and local Ollama.
- **In-App Settings Modal**: Configure or switch API keys, models, and providers directly from the UI without restarting the server.
- **Multimodal Uploads**: Upload documents, text files, and images with automatic vision / content analysis.
- **Combine & Analyse**: Select and compare two conversation threads to synthesize key insights and recommendations.
- **Rich Markdown & Code Highlighting**: Syntax styling for code snippets with single-click copy buttons, formatted headers, lists, and blockquotes.
- **Voice Input**: Speech-to-text input via the microphone button (Web Speech API).
- **Conversation Management**: Delete individual threads or clear history.
- **Mock Mode Fallback**: Runs with sample structured responses if no API key is provided yet.

---

## API Reference

| Method | Path               | Description                                  |
|--------|--------------------|----------------------------------------------|
| `GET`  | `/health`          | Server health, active provider, model & mode |
| `GET`  | `/api/config`      | Read current configuration & key status      |
| `POST` | `/api/config`      | Update provider, API key, model, & base URL  |
| `POST` | `/chat`            | Multi-turn conversation endpoint             |
| `POST` | `/upload`          | File / image upload + analysis               |
| `POST` | `/combine-analyze` | Compare and synthesize two conversation logs |
| `GET`  | `/`                | Serves frontend `index.html`                 |
