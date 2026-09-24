"""
XAI FastAPI backend — streaming chat, file upload, combine-analyse, and configuration endpoints.
Supports Google Gemini via direct REST API with real-time SSE token streaming as well as
OpenAI-compatible providers (OpenAI, Groq, OpenRouter, DeepSeek, Ollama, etc.).
"""

from __future__ import annotations

from pathlib import Path
import asyncio
import base64
import json
import os
import re
import traceback
from typing import Any, AsyncGenerator, List, Optional

import httpx
from dotenv import load_dotenv, set_key
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="XAI Backend", version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Provider & Model Configuration
# ---------------------------------------------------------------------------
ENV_FILE_PATH = Path(__file__).resolve().parent / ".env"

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip()

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
}

def get_active_provider() -> str:
    return AI_PROVIDER

def get_active_model() -> str:
    if AI_PROVIDER == "gemini":
        return GEMINI_MODEL or "gemini-3.6-flash"
    return AI_MODEL or "default"

def get_base_url() -> str:
    if AI_BASE_URL:
        return AI_BASE_URL
    return PROVIDER_BASE_URLS.get(AI_PROVIDER, "https://api.openai.com/v1")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    chat_id: str
    message: str
    history: List[HistoryMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str


class CombineRequest(BaseModel):
    chat_a: List[HistoryMessage]
    chat_b: List[HistoryMessage]


class CombineResponse(BaseModel):
    analysis: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    mode: str
    has_key: bool


class ConfigUpdateRequest(BaseModel):
    provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_base_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers & Streaming Generators
# ---------------------------------------------------------------------------
def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _mock_answer(user_message: str, context: str = "") -> str:
    preview = (user_message or "").strip()[:120]
    extra = f"\n\nContext note: {context}" if context else ""
    return (
        f"**[Mock Mode — Running without live API key]**\n\n"
        f"You asked: *\"{preview}\"*\n\n"
        "Here is a structured explanation:\n"
        "1. **Core Concept**: Explainable AI bridges the gap between complex model predictions and human understanding.\n"
        "2. **Key Insights**: Provides actionable transparency, accountability, and debugging capability.\n"
        "3. **Practical Value**: Improves trust and enables safety verification for production applications.\n\n"
        "💡 *To enable live AI responses, open **Settings** (or edit `.env`) and add your Gemini or OpenAI API key.*"
        f"{extra}"
    )


async def _stream_mock(user_message: str, context: str = "") -> AsyncGenerator[str, None]:
    full_text = _mock_answer(user_message, context)
    words = re.findall(r'\S+|\n+', full_text)
    for i, w in enumerate(words):
        space = "" if (w.startswith("\n") or (i > 0 and words[i - 1].endswith("\n"))) else " "
        yield (space + w) if i > 0 else w
        await asyncio.sleep(0.015)


def _format_gemini_model_name(model: str) -> str:
    clean = model.strip()
    if clean.startswith("models/"):
        return clean.replace("models/", "")
    return clean


async def _stream_gemini(
    prompt: str,
    history: Optional[List[HistoryMessage]] = None,
    parts_extra: Optional[List[dict[str, Any]]] = None,
) -> AsyncGenerator[str, None]:
    """Stream Gemini response token by token using SSE REST API."""
    global GEMINI_MODEL
    if not GEMINI_API_KEY:
        async for chunk in _stream_mock(prompt):
            yield chunk
        return

    primary_model = _format_gemini_model_name(GEMINI_MODEL or "gemini-3.6-flash")
    fallback_models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-flash-latest",
        "gemma-4-31b-it",
    ]
    candidate_models = [primary_model] + [m for m in fallback_models if m != primary_model]

    contents: list[dict[str, Any]] = []

    # Format multi-turn history
    if history:
        for m in history:
            role = "user" if m.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.content}]
            })

    # Current user turn
    current_parts: list[dict[str, Any]] = []
    if parts_extra:
        current_parts.extend(parts_extra)
    if prompt:
        current_parts.append({"text": prompt})

    if not current_parts:
        current_parts.append({"text": "Hello"})

    contents.append({
        "role": "user",
        "parts": current_parts
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }

    last_err_msg = ""
    last_status = 502
    streamed_anything = False

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
            try:
                resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                target_payload = payload
                if resp.status_code == 400 and "thinkingConfig" in target_payload.get("generationConfig", {}):
                    target_payload = {
                        "contents": contents,
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 4096,
                        },
                        "safetySettings": payload["safetySettings"],
                    }

                async with client.stream("POST", url, json=target_payload, headers={"Content-Type": "application/json"}) as stream_resp:
                    if stream_resp.status_code == 200:
                        if model_name != GEMINI_MODEL:
                            GEMINI_MODEL = model_name

                        async for line in stream_resp.aiter_lines():
                            if line.startswith("data: "):
                                raw_json = line[6:].strip()
                                if not raw_json:
                                    continue
                                try:
                                    chunk_data = json.loads(raw_json)
                                    candidates = chunk_data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        for part in parts:
                                            text_delta = part.get("text", "")
                                            if text_delta:
                                                streamed_anything = True
                                                yield text_delta
                                    else:
                                        block_reason = chunk_data.get("promptFeedback", {}).get("blockReason")
                                        if block_reason:
                                            streamed_anything = True
                                            yield f"[Gemini blocked this request: {block_reason}]"
                                except Exception:
                                    pass
                        return
                    else:
                        last_status = stream_resp.status_code
                        err_body = await stream_resp.aread()
                        err_text = err_body.decode("utf-8", errors="replace")
                        try:
                            err_json = json.loads(err_text)
                            last_err_msg = err_json.get("error", {}).get("message", err_text)
                        except Exception:
                            last_err_msg = err_text
                        except Exception:
                            last_err_msg = err_text

                        if resp.status_code in (401, 403):
                            break
            except httpx.RequestError as exc:
                last_err_msg = f"Network error contacting {model_name}: {exc}"
                continue

    if not streamed_anything:
        yield f"[Gemini Error ({last_status}): {last_err_msg or 'Failed to generate response'}]"


async def _stream_openai_compatible(
    messages: list[dict[str, Any]],
    model_name: Optional[str] = None
) -> AsyncGenerator[str, None]:
    target_model = model_name or AI_MODEL or "gpt-4o-mini"
    base_url = get_base_url().rstrip("/")
    endpoint = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.7,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            async with client.stream("POST", endpoint, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    err_text = err_body.decode("utf-8", errors="replace")
                    try:
                        err_json = json.loads(err_text)
                        err_msg = err_json.get("error", {}).get("message", err_text)
                    except Exception:
                        err_msg = err_text
                    yield f"[{AI_PROVIDER.capitalize()} API Error ({resp.status_code}): {err_msg}]"
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except Exception:
                            pass
        except httpx.RequestError as exc:
            yield f"[Network error contacting {AI_PROVIDER}: {exc}]"


async def _stream_text(
    prompt: str,
    history: Optional[List[HistoryMessage]] = None
) -> AsyncGenerator[str, None]:
    if AI_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            async for chunk in _stream_mock(prompt):
                yield chunk
            return
        async for chunk in _stream_gemini(prompt, history=history):
            yield chunk
        return

    if AI_API_KEY or AI_PROVIDER == "ollama":
        messages: list[dict[str, Any]] = []
        if history:
            for m in history:
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": prompt})
        async for chunk in _stream_openai_compatible(messages):
            yield chunk
        return

    async for chunk in _stream_mock(prompt):
        yield chunk


async def _stream_with_file(
    message: str,
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> AsyncGenerator[str, None]:
    # 1. Gemini with file
    if AI_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            async for chunk in _stream_mock(
                message,
                context=f"File received: {filename} ({mime_type}, {len(file_bytes)} bytes)",
            ):
                yield chunk
            return

        if mime_type.startswith("image/"):
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            parts_extra = [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_data,
                    }
                }
            ]
            prompt = message or "Describe this image in detail and explain the key components."
            async for chunk in _stream_gemini(prompt, parts_extra=parts_extra):
                yield chunk
            return
        else:
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                if len(text_content) > 100_000:
                    text_content = text_content[:100_000] + "\n...[truncated remainder of file]"
                prompt = (
                    f"The user uploaded a document named “{filename}”.\n\n"
                    f"Document contents:\n```\n{text_content}\n```\n\n"
                    f"User prompt: {message or 'Analyze this document and explain the key findings, structure, and takeaways.'}"
                )
            except Exception:
                prompt = (
                    f"The user uploaded a binary file “{filename}” ({mime_type}, {len(file_bytes)} bytes).\n"
                    f"{message or 'Analyze what you can from this file.'}"
                )
            async for chunk in _stream_gemini(prompt):
                yield chunk
            return

    # 2. OpenAI-compatible provider with file
    if AI_API_KEY or AI_PROVIDER == "ollama":
        if mime_type.startswith("image/"):
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            image_url = f"data:{mime_type};base64,{b64_img}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message or "Describe this image and analyze its key components."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
        else:
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                if len(text_content) > 100_000:
                    text_content = text_content[:100_000] + "\n...[truncated remainder of file]"
                prompt = (
                    f"The user uploaded a document named “{filename}”.\n\n"
                    f"Document contents:\n```\n{text_content}\n```\n\n"
                    f"User prompt: {message or 'Analyze this document and explain the key findings, structure, and takeaways.'}"
                )
            except Exception:
                prompt = (
                    f"The user uploaded a file named “{filename}” ({mime_type}, {len(file_bytes)} bytes).\n"
                    f"{message or 'Analyze what you can.'}"
                )
            messages = [{"role": "user", "content": prompt}]

        async for chunk in _stream_openai_compatible(messages):
            yield chunk
        return

    async for chunk in _stream_mock(
        message,
        context=f"File received: {filename} ({mime_type}, {len(file_bytes)} bytes)",
    ):
        yield chunk


async def _stream_sse_response(generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    try:
        async for chunk in generator:
            yield _sse_event({"delta": chunk})
        yield _sse_event({"done": True})
    except Exception as exc:
        traceback.print_exc()
        yield _sse_event({"error": str(exc), "done": True})


async def _generate_text(prompt: str, history: Optional[List[HistoryMessage]] = None) -> str:
    chunks = []
    async for chunk in _stream_text(prompt, history=history):
        chunks.append(chunk)
    return "".join(chunks).strip() or "[Empty response]"


async def _generate_with_file(
    message: str,
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> str:
    chunks = []
    async for chunk in _stream_with_file(message, file_bytes, mime_type, filename):
        chunks.append(chunk)
    return "".join(chunks).strip() or "[Empty response]"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    has_key = bool((AI_PROVIDER == "gemini" and GEMINI_API_KEY) or (AI_PROVIDER != "gemini" and (AI_API_KEY or AI_PROVIDER == "ollama")))
    active_mode = "live" if has_key else "mock"
    return HealthResponse(
        status="ok",
        provider=AI_PROVIDER,
        model=get_active_model(),
        mode=active_mode,
        has_key=has_key,
    )


@app.get("/api/config")
def get_config():
    return {
        "provider": AI_PROVIDER,
        "gemini_model": GEMINI_MODEL,
        "gemini_key_set": bool(GEMINI_API_KEY),
        "ai_model": AI_MODEL,
        "ai_base_url": AI_BASE_URL,
        "ai_key_set": bool(AI_API_KEY),
        "mode": "live" if bool((AI_PROVIDER == "gemini" and GEMINI_API_KEY) or (AI_PROVIDER != "gemini" and (AI_API_KEY or AI_PROVIDER == "ollama"))) else "mock"
    }


@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    global AI_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, AI_API_KEY, AI_MODEL, AI_BASE_URL

    if req.provider:
        AI_PROVIDER = req.provider.strip().lower()
    if req.gemini_api_key is not None:
        GEMINI_API_KEY = req.gemini_api_key.strip()
    if req.gemini_model:
        GEMINI_MODEL = req.gemini_model.strip()
    if req.ai_api_key is not None:
        AI_API_KEY = req.ai_api_key.strip()
    if req.ai_model:
        AI_MODEL = req.ai_model.strip()
    if req.ai_base_url is not None:
        AI_BASE_URL = req.ai_base_url.strip()

    # Save to .env if file exists
    try:
        if not ENV_FILE_PATH.is_file():
            ENV_FILE_PATH.touch()
        set_key(str(ENV_FILE_PATH), "AI_PROVIDER", AI_PROVIDER)
        if GEMINI_API_KEY:
            set_key(str(ENV_FILE_PATH), "GEMINI_API_KEY", GEMINI_API_KEY)
        if GEMINI_MODEL:
            set_key(str(ENV_FILE_PATH), "GEMINI_MODEL", GEMINI_MODEL)
        if AI_API_KEY:
            set_key(str(ENV_FILE_PATH), "AI_API_KEY", AI_API_KEY)
        if AI_MODEL:
            set_key(str(ENV_FILE_PATH), "AI_MODEL", AI_MODEL)
        if AI_BASE_URL:
            set_key(str(ENV_FILE_PATH), "AI_BASE_URL", AI_BASE_URL)
    except Exception as e:
        print(f"[XAI] Could not write to .env file: {e}")

    return {
        "success": True,
        "provider": AI_PROVIDER,
        "model": get_active_model(),
        "mode": "live" if bool((AI_PROVIDER == "gemini" and GEMINI_API_KEY) or (AI_PROVIDER != "gemini" and (AI_API_KEY or AI_PROVIDER == "ollama"))) else "mock"
    }


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    async def sse_gen():
        generator = _stream_text(req.message, history=req.history)
        async for sse in _stream_sse_response(generator):
            yield sse

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    answer = await _generate_text(req.message, history=req.history)
    return ChatResponse(answer=answer)


@app.post("/upload/stream")
async def upload_stream(
    file: UploadFile = File(...),
    message: str = Form("Analyze this file and explain the important points."),
    chat_id: str = Form(""),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    mime = file.content_type or "application/octet-stream"

    async def sse_gen():
        generator = _stream_with_file(message, raw, mime, file.filename or "upload")
        async for sse in _stream_sse_response(generator):
            yield sse

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/upload", response_model=ChatResponse)
async def upload(
    file: UploadFile = File(...),
    message: str = Form("Analyze this file and explain the important points."),
    chat_id: str = Form(""),
) -> ChatResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    mime = file.content_type or "application/octet-stream"
    answer = await _generate_with_file(message, raw, mime, file.filename or "upload")
    return ChatResponse(answer=answer)


@app.post("/combine-analyze/stream")
async def combine_analyze_stream(req: CombineRequest):
    def fmt(msgs: List[HistoryMessage]) -> str:
        lines = []
        for m in msgs:
            lines.append(f"{m.role.upper()}: {m.content}")
        return "\n".join(lines) or "(empty)"

    prompt = (
        "You are an expert analytical AI. Compare and synthesize the two conversations below.\n"
        "Provide a rich, structured breakdown with the following sections in Markdown:\n\n"
        "### 1. 📌 Core Topics & Focus\n"
        "Summarize the key question or subject explored in each thread.\n\n"
        "### 2. ⚖️ Commonalities & Contrasts\n"
        "Highlight points of agreement, divergent perspectives, or differing methodologies.\n\n"
        "### 3. 💡 Synergistic Insights\n"
        "Explain how the two conversations inform or enhance one another.\n\n"
        "### 4. 🎯 Unified Synthesis & Next Steps\n"
        "Provide actionable conclusions and recommendations based on both threads combined.\n\n"
        "=== Conversation A ===\n"
        f"{fmt(req.chat_a)}\n\n"
        "=== Conversation B ===\n"
        f"{fmt(req.chat_b)}\n"
    )

    async def sse_gen():
        generator = _stream_text(prompt)
        async for sse in _stream_sse_response(generator):
            yield sse

    return StreamingResponse(
        sse_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/combine-analyze", response_model=CombineResponse)
async def combine_analyze(req: CombineRequest) -> CombineResponse:
    def fmt(msgs: List[HistoryMessage]) -> str:
        lines = []
        for m in msgs:
            lines.append(f"{m.role.upper()}: {m.content}")
        return "\n".join(lines) or "(empty)"

    prompt = (
        "You are an expert analytical AI. Compare and synthesize the two conversations below.\n"
        "Provide a rich, structured breakdown with the following sections in Markdown:\n\n"
        "### 1. 📌 Core Topics & Focus\n"
        "Summarize the key question or subject explored in each thread.\n\n"
        "### 2. ⚖️ Commonalities & Contrasts\n"
        "Highlight points of agreement, divergent perspectives, or differing methodologies.\n\n"
        "### 3. 💡 Synergistic Insights\n"
        "Explain how the two conversations inform or enhance one another.\n\n"
        "### 4. 🎯 Unified Synthesis & Next Steps\n"
        "Provide actionable conclusions and recommendations based on both threads combined.\n\n"
        "=== Conversation A ===\n"
        f"{fmt(req.chat_a)}\n\n"
        "=== Conversation B ===\n"
        f"{fmt(req.chat_b)}\n"
    )

    analysis = await _generate_text(prompt)
    return CombineResponse(analysis=analysis)


# ---------------------------------------------------------------------------
# Serve frontend assets
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = CURRENT_DIR if (CURRENT_DIR / "index.html").is_file() else (CURRENT_DIR.parent / "frontend")


@app.get("/")
def root():
    index = FRONTEND_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {
        "service": "XAI Backend",
        "docs": "/docs",
        "health": "/health",
        "hint": f"index.html not found in {FRONTEND_DIR}",
    }


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/styles.css")
    def styles():
        css_file = FRONTEND_DIR / "styles.css"
        if css_file.is_file():
            return FileResponse(css_file, media_type="text/css")
        raise HTTPException(status_code=404, detail="styles.css not found")

    @app.get("/script.js")
    def script():
        js_file = FRONTEND_DIR / "script.js"
        if js_file.is_file():
            return FileResponse(js_file, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="script.js not found")

    @app.get("/favicon.svg")
    def favicon_svg():
        svg_file = FRONTEND_DIR / "favicon.svg"
        if svg_file.is_file():
            return FileResponse(svg_file, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="favicon.svg not found")

    @app.get("/favicon.ico")
    def favicon_ico():
        svg_file = FRONTEND_DIR / "favicon.svg"
        if svg_file.is_file():
            return FileResponse(svg_file, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="favicon.ico not found")
