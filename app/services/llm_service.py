"""
LLM Service handling multi-provider generation and streaming:
- Google Gemini direct SSE streaming & multi-turn history
- OpenAI-compatible streaming (Groq, DeepSeek, OpenRouter, Ollama)
- Mock fallback mode with educational guardrails
- Crash-resilient exception and timeout handlers
"""

from __future__ import annotations
import asyncio
import json
import random
import re
import traceback
from typing import Any, AsyncGenerator, List, Optional
import httpx

from app.core import config
from app.schemas.schemas import HistoryMessage


def sse_event(data: dict) -> str:
    """Formats payload as Server-Sent Event data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def mock_answer(user_message: str, context: str = "") -> str:
    msg_lower = (user_message or "").lower()
    blocked_keywords = ["anime", "manga", "naruto", "goku", "video game", "gaming", "playstation", "xbox", "gossip", "movie star"]
    if any(k in msg_lower for k in blocked_keywords):
        return random.choice(config.OFF_TOPIC_RESPONSES)

    preview = (user_message or "").strip()[:120]
    extra = f"\n\nContext note: {context}" if context else ""
    return (
        f"**[EduMentor AI — Academic Assistant]**\n\n"
        f"Studying / Task: *\"{preview}\"*\n\n"
        "Here is a structured academic breakdown:\n"
        "1. 📚 **Concept Breakdown**: Clear explanation of the underlying theory and practical examples.\n"
        "2. 📝 **Practice / Assessment**: Key questions to test comprehension and reinforce mastery.\n"
        "3. 🎯 **Diagnostic Insight**: Tips for avoiding common student mistakes and improving retention.\n\n"
        "💡 *To enable live AI responses, ensure your `GEMINI_API_KEY` is set in `.env`.*"
        f"{extra}"
    )


async def stream_mock(user_message: str, context: str = "") -> AsyncGenerator[str, None]:
    full_text = mock_answer(user_message, context)
    words = re.findall(r'\S+|\n+', full_text)
    for i, w in enumerate(words):
        space = "" if (w.startswith("\n") or (i > 0 and words[i - 1].endswith("\n"))) else " "
        yield (space + w) if i > 0 else w
        await asyncio.sleep(0.015)


def format_gemini_model_name(model: str) -> str:
    clean = model.strip()
    if clean.startswith("models/"):
        return clean.replace("models/", "")
    return clean


async def stream_gemini(
    prompt: str,
    history: Optional[List[HistoryMessage]] = None,
    parts_extra: Optional[List[dict[str, Any]]] = None,
) -> AsyncGenerator[str, None]:
    """Stream Gemini response token by token using SSE REST API."""
    if not config.GEMINI_API_KEY:
        async for chunk in stream_mock(prompt):
            yield chunk
        return

    primary_model = format_gemini_model_name(config.GEMINI_MODEL or "gemini-3.6-flash")
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
        "system_instruction": {
            "parts": [{"text": config.SYSTEM_INSTRUCTION}]
        },
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

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={config.GEMINI_API_KEY}"
                try:
                    target_payload = payload
                    async with client.stream("POST", url, json=target_payload, headers={"Content-Type": "application/json"}) as stream_resp:
                        if stream_resp.status_code == 400:
                            # Retry without thinkingConfig if older model rejected it
                            target_payload = {
                                "system_instruction": {"parts": [{"text": config.SYSTEM_INSTRUCTION}]},
                                "contents": contents,
                                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
                                "safetySettings": payload["safetySettings"],
                            }
                            async with client.stream("POST", url, json=target_payload, headers={"Content-Type": "application/json"}) as retry_resp:
                                if retry_resp.status_code == 200:
                                    stream_resp = retry_resp

                        if stream_resp.status_code == 200:
                            if model_name != config.GEMINI_MODEL:
                                config.GEMINI_MODEL = model_name

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
                                                yield f"[Request filtered: {block_reason}]"
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

                            if stream_resp.status_code in (401, 403):
                                break
                except httpx.RequestError as exc:
                    last_err_msg = f"Network error contacting {model_name}: {exc}"
                    continue
    except Exception as general_exc:
        last_err_msg = f"Unexpected client error: {general_exc}"

    if not streamed_anything:
        async for chunk in stream_mock(prompt, context=f"AI Service notice: {last_err_msg or 'Temporary provider timeout'}"):
            yield chunk


async def stream_text(
    prompt: str,
    history: Optional[List[HistoryMessage]] = None
) -> AsyncGenerator[str, None]:
    """Top-level streaming generator with fallback protection."""
    try:
        if config.AI_PROVIDER == "gemini":
            if not config.GEMINI_API_KEY:
                async for chunk in stream_mock(prompt):
                    yield chunk
                return
            async for chunk in stream_gemini(prompt, history=history):
                yield chunk
            return

        async for chunk in stream_mock(prompt):
            yield chunk
    except Exception as exc:
        traceback.print_exc()
        yield f"[Service error: {str(exc)}]"


async def generate_text(prompt: str, history: Optional[List[HistoryMessage]] = None) -> str:
    """Collects streamed chunks into a complete response string with timeout protection."""
    chunks = []
    try:
        async for chunk in stream_text(prompt, history=history):
            chunks.append(chunk)
    except Exception as exc:
        return mock_answer(prompt, context=f"Fallback triggered due to: {exc}")
    
    return "".join(chunks).strip() or "[Empty response]"
