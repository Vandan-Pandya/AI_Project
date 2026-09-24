// ---------------------------------------------------------------------------
// XAI frontend <-> FastAPI backend wiring with Real-time SSE Streaming
// ---------------------------------------------------------------------------
const API_BASE = window.XAI_API_BASE != null
  ? window.XAI_API_BASE
  : (location.protocol === "file:" ? "http://127.0.0.1:8000" : "");

// In-memory client-side store of conversations
// Shape: { [chatId]: { id, title, timeLabel, messages: [{role, content}] } }
const chats = {};
let currentChatId = null;
let pendingFile = null; // { file, kind: 'device' | 'image' | 'camera' }

// ---------------------------------------------------------------------------
// Element refs
// ---------------------------------------------------------------------------
const heroIntro = document.getElementById('heroIntro');
const chatThread = document.getElementById('chatThread');
const messageList = document.getElementById('messageList');
const historyList = document.getElementById('historyList');
const historyEmpty = document.getElementById('historyEmpty');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');

const composerInput = document.getElementById('composerInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');

const attachToggle = document.getElementById('attachToggle');
const attachMenu = document.getElementById('attachMenu');
const attachOptions = document.querySelectorAll('.attach-option');
const imageAttachBtn = document.getElementById('imageAttachBtn');
const micBtn = document.getElementById('micBtn');

const fileInputDevice = document.getElementById('fileInputDevice');
const fileInputImage = document.getElementById('fileInputImage');
const fileInputCamera = document.getElementById('fileInputCamera');

const fileChip = document.getElementById('fileChip');
const fileChipName = document.getElementById('fileChipName');
const fileChipRemove = document.getElementById('fileChipRemove');

const connectionToast = document.getElementById('connectionToast');

const cardAsk = document.getElementById('cardAsk');
const cardUpload = document.getElementById('cardUpload');
const cardCombine = document.getElementById('cardCombine');
const cardInsights = document.getElementById('cardInsights');

// Topbar badge & settings buttons
const modelBadge = document.getElementById('modelBadge');
const badgeProviderText = document.getElementById('badgeProviderText');
const badgeModelText = document.getElementById('badgeModelText');
const badgeModeTag = document.getElementById('badgeModeTag');
const quickSettingsBtn = document.getElementById('quickSettingsBtn');
const settingsBtn = document.getElementById('settingsBtn');

// Combine modal refs
const combineOverlay = document.getElementById('combineOverlay');
const combineList = document.getElementById('combineList');
const combineCancel = document.getElementById('combineCancel');
const combineRun = document.getElementById('combineRun');
const combineClose = document.getElementById('combineClose');
const combineSidebarBtn = document.getElementById('combineSidebarBtn');

// Settings modal refs
const settingsOverlay = document.getElementById('settingsOverlay');
const settingsClose = document.getElementById('settingsClose');
const settingsCancel = document.getElementById('settingsCancel');
const settingsSave = document.getElementById('settingsSave');
const settingsForm = document.getElementById('settingsForm');
const cfgProvider = document.getElementById('cfgProvider');
const geminiSection = document.getElementById('geminiSection');
const genericSection = document.getElementById('genericSection');
const cfgGeminiKey = document.getElementById('cfgGeminiKey');
const cfgGeminiModel = document.getElementById('cfgGeminiModel');
const cfgGeminiModelCustom = document.getElementById('cfgGeminiModelCustom');
const cfgAiKey = document.getElementById('cfgAiKey');
const cfgAiModel = document.getElementById('cfgAiModel');
const cfgAiBaseUrl = document.getElementById('cfgAiBaseUrl');
const toggleGeminiKeyVis = document.getElementById('toggleGeminiKeyVis');
const toggleAiKeyVis = document.getElementById('toggleAiKeyVis');
const settingsStatusMsg = document.getElementById('settingsStatusMsg');

// ---------------------------------------------------------------------------
// Markdown Parser & Formatter
// ---------------------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function parseMarkdown(text) {
  if (!text) return '';

  let html = text;

  // Extract completed code blocks first to protect formatting
  const codeBlocks = [];
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    const cleanLang = (lang || 'code').trim().toLowerCase();
    const cleanCode = escapeHtml(code.replace(/\n$/, ''));
    codeBlocks.push(`
      <div class="code-block-wrapper">
        <div class="code-block-header">
          <span>${cleanLang}</span>
          <button class="copy-code-btn" type="button" onclick="copyCodeBlock(this)">Copy</button>
        </div>
        <pre><code class="language-${cleanLang}">${cleanCode}</code></pre>
      </div>
    `);
    return placeholder;
  });

  // Handle unclosed code block during live streaming
  const openCodeBlockMatch = html.match(/```([a-zA-Z0-9_-]*)\n([\s\S]*)$/);
  if (openCodeBlockMatch) {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    const cleanLang = (openCodeBlockMatch[1] || 'code').trim().toLowerCase();
    const cleanCode = escapeHtml(openCodeBlockMatch[2]);
    codeBlocks.push(`
      <div class="code-block-wrapper">
        <div class="code-block-header">
          <span>${cleanLang}</span>
          <button class="copy-code-btn" type="button" onclick="copyCodeBlock(this)">Copy</button>
        </div>
        <pre><code class="language-${cleanLang}">${cleanCode}</code></pre>
      </div>
    `);
    html = html.substring(0, openCodeBlockMatch.index) + placeholder;
  }

  // Inline code
  html = html.replace(/`([^`]+)`/g, (match, code) => {
    return `<code class="inline-code">${escapeHtml(code)}</code>`;
  });

  // Headers (h3, h2, h1)
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold and Italics
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  html = html.replace(/_([^_]+)_/g, '<em>$1</em>');

  // Blockquotes
  html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Unordered list items
  html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, '');

  // Ordered list items
  html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

  // Paragraphs
  const lines = html.split(/\n\n+/);
  html = lines.map(block => {
    block = block.trim();
    if (!block) return '';
    if (
      block.startsWith('<h') ||
      block.startsWith('<ul') ||
      block.startsWith('<ol') ||
      block.startsWith('<blockquote') ||
      block.startsWith('__CODE_BLOCK_')
    ) {
      return block;
    }
    return `<p>${block.replace(/\n/g, '<br/>')}</p>`;
  }).join('\n');

  // Restore code blocks
  codeBlocks.forEach((blockHtml, index) => {
    html = html.replace(`__CODE_BLOCK_${index}__`, blockHtml);
    html = html.replace(`<p>__CODE_BLOCK_${index}__</p>`, blockHtml);
  });

  return html;
}

window.copyCodeBlock = function (btn) {
  const wrapper = btn.closest('.code-block-wrapper');
  if (!wrapper) return;
  const codeEl = wrapper.querySelector('pre code');
  if (!codeEl) return;

  navigator.clipboard.writeText(codeEl.textContent).then(() => {
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => {
      btn.textContent = originalText;
    }, 2000);
  }).catch(err => {
    console.error('Copy failed:', err);
  });
};

// ---------------------------------------------------------------------------
// Health check & Config state
// ---------------------------------------------------------------------------
async function checkBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('unhealthy');
    const data = await res.json();
    console.log('[XAI] Backend status:', data);
    updateModelBadge(data.provider, data.model, data.mode);
  } catch (err) {
    console.error('[XAI] Health check failed:', err);
    updateModelBadge('Disconnected', 'offline', 'mock');
    showToast(`Cannot reach backend at ${API_BASE}. Start with: uvicorn main:app --reload`);
  }
}

function updateModelBadge(provider, model, mode) {
  if (badgeProviderText) badgeProviderText.textContent = provider.toUpperCase();
  if (badgeModelText) badgeModelText.textContent = model || 'gemini-3.6-flash';
  if (badgeModeTag) {
    badgeModeTag.textContent = (mode || 'LIVE').toUpperCase();
    badgeModeTag.classList.toggle('mock', mode === 'mock');
  }
  const dot = document.querySelector('.badge-dot');
  if (dot) {
    dot.classList.toggle('mock', mode === 'mock');
  }
}

let toastTimer = null;
function showToast(message, ms = 7000) {
  if (!connectionToast) return;
  connectionToast.textContent = message;
  connectionToast.hidden = false;
  connectionToast.style.cursor = "pointer";
  if (toastTimer) clearTimeout(toastTimer);
  if (ms > 0) toastTimer = setTimeout(hideToast, ms);
}

function hideToast() {
  if (!connectionToast) return;
  connectionToast.hidden = true;
  if (toastTimer) clearTimeout(toastTimer);
}

if (connectionToast) {
  connectionToast.addEventListener("click", hideToast);
}

checkBackend();

// ---------------------------------------------------------------------------
// View helpers
// ---------------------------------------------------------------------------
function showChatView() {
  heroIntro.hidden = true;
  chatThread.hidden = false;
}

function showHeroView() {
  heroIntro.hidden = false;
  chatThread.hidden = true;
  messageList.innerHTML = '';
}

function scrollToBottom() {
  messageList.scrollTop = messageList.scrollHeight;
}

function renderMessage(role, content, opts = {}) {
  const row = document.createElement('div');
  row.className = `message-row ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble' + (opts.error ? ' error' : '');

  if (opts.attachmentName) {
    const chip = document.createElement('div');
    chip.className = 'message-attachment';
    chip.textContent = `📎 ${opts.attachmentName}`;
    bubble.appendChild(chip);
  }

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  if (role === 'assistant' && !opts.error) {
    contentDiv.innerHTML = parseMarkdown(content);
  } else {
    contentDiv.textContent = content;
  }

  bubble.appendChild(contentDiv);
  row.appendChild(bubble);
  messageList.appendChild(row);
  scrollToBottom();
  return row;
}

function renderTyping() {
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = 'typingRow';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';

  row.appendChild(bubble);
  messageList.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  const row = document.getElementById('typingRow');
  if (row) row.remove();
}

// ---------------------------------------------------------------------------
// History sidebar
// ---------------------------------------------------------------------------
function chatIcon() {
  return `<svg class="chat-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
    <path d="M21 12C21 16.4183 16.9706 20 12 20C10.5257 20 9.13385 19.6905 7.90621 19.1379L3 20L4.39638 16.3187C3.51554 15.0301 3 13.5722 3 12C3 7.58172 7.02944 4 12 4C16.9706 4 21 7.58172 21 12Z"/>
  </svg>`;
}

function addHistoryEntry(chatId, title, timeLabel = 'Just now') {
  if (historyEmpty) historyEmpty.hidden = true;

  const btn = document.createElement('div');
  btn.className = 'history-item real';
  btn.dataset.chatId = chatId;
  btn.innerHTML = `
    ${chatIcon()}
    <span class="history-text"></span>
    <span class="history-time">${timeLabel}</span>
    <button class="history-delete-btn" title="Delete conversation" aria-label="Delete conversation">&times;</button>
  `;
  btn.querySelector('.history-text').textContent = title;

  btn.addEventListener('click', (e) => {
    if (e.target.classList.contains('history-delete-btn')) {
      e.stopPropagation();
      deleteChat(chatId);
      return;
    }
    loadChat(chatId);
  });

  historyList.prepend(btn);
  setActiveHistory(chatId);
}

function setActiveHistory(chatId) {
  document.querySelectorAll('.history-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.chatId === chatId);
  });
}

function updateHistoryTitle(chatId, title) {
  const item = historyList.querySelector(`[data-chat-id="${chatId}"] .history-text`);
  if (item) item.textContent = title;
}

function loadChat(chatId) {
  const chat = chats[chatId];
  if (!chat) return;

  currentChatId = chatId;
  setActiveHistory(chatId);
  showChatView();
  messageList.innerHTML = '';
  chat.messages.forEach((m) => renderMessage(m.role === 'user' ? 'user' : 'assistant', m.content));
}

function deleteChat(chatId) {
  delete chats[chatId];
  const el = historyList.querySelector(`[data-chat-id="${chatId}"]`);
  if (el) el.remove();

  if (currentChatId === chatId) {
    currentChatId = null;
    showHeroView();
  }

  if (Object.keys(chats).length === 0 && historyEmpty) {
    historyEmpty.hidden = false;
  }
}

if (clearHistoryBtn) {
  clearHistoryBtn.addEventListener('click', () => {
    if (Object.keys(chats).length === 0) return;
    if (confirm('Clear all conversation history?')) {
      for (const id in chats) delete chats[id];
      historyList.innerHTML = '';
      if (historyEmpty) historyEmpty.hidden = false;
      currentChatId = null;
      showHeroView();
    }
  });
}

// ---------------------------------------------------------------------------
// New chat
// ---------------------------------------------------------------------------
if (newChatBtn) {
  newChatBtn.addEventListener('click', () => {
    currentChatId = null;
    pendingFile = null;
    hideFileChip();
    document.querySelectorAll('.history-item').forEach((item) => item.classList.remove('active'));
    showHeroView();
    composerInput.focus();
  });
}

// ---------------------------------------------------------------------------
// Feature cards
// ---------------------------------------------------------------------------
if (cardAsk) cardAsk.addEventListener('click', () => composerInput.focus());

if (cardUpload) {
  cardUpload.addEventListener('click', () => {
    attachMenu.classList.add('open');
    attachToggle.setAttribute('aria-expanded', 'true');
  });
}

if (cardCombine) cardCombine.addEventListener('click', openCombineModal);
if (combineSidebarBtn) combineSidebarBtn.addEventListener('click', openCombineModal);

if (cardInsights) {
  cardInsights.addEventListener('click', () => {
    composerInput.focus();
    composerInput.value = 'Explain the key trade-offs and deep underlying principles of ';
  });
}

// ---------------------------------------------------------------------------
// Attach menu + file selection
// ---------------------------------------------------------------------------
function closeAttachMenu() {
  if (attachMenu) {
    attachMenu.classList.remove('open');
    if (attachToggle) attachToggle.setAttribute('aria-expanded', 'false');
  }
}

if (attachToggle) {
  attachToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = attachMenu.classList.toggle('open');
    attachToggle.setAttribute('aria-expanded', String(isOpen));
  });
}

document.addEventListener('click', (e) => {
  if (attachMenu && !attachMenu.contains(e.target) && e.target !== attachToggle) {
    closeAttachMenu();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeAttachMenu();
    closeCombineModal();
    closeSettingsModal();
  }
});

if (attachOptions.length >= 3) {
  attachOptions[0].addEventListener('click', () => { fileInputDevice.click(); closeAttachMenu(); });
  attachOptions[1].addEventListener('click', () => { fileInputImage.click(); closeAttachMenu(); });
  attachOptions[2].addEventListener('click', () => { fileInputCamera.click(); closeAttachMenu(); });
}
if (imageAttachBtn) imageAttachBtn.addEventListener('click', () => fileInputImage.click());

[fileInputDevice, fileInputImage, fileInputCamera].forEach((input) => {
  if (!input) return;
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (file) setPendingFile(file);
    input.value = '';
  });
});

function setPendingFile(file) {
  pendingFile = file;
  fileChipName.textContent = file.name;
  fileChip.hidden = false;
}

function hideFileChip() {
  if (!fileChip) return;
  fileChip.hidden = true;
  fileChipName.textContent = '';
}

if (fileChipRemove) {
  fileChipRemove.addEventListener('click', () => {
    pendingFile = null;
    hideFileChip();
  });
}

// ---------------------------------------------------------------------------
// Voice Input (Web Speech API)
// ---------------------------------------------------------------------------
let recognition = null;
let isRecording = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    micBtn.classList.add('recording');
    micBtn.title = 'Listening... click to stop';
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    if (composerInput.value) {
      composerInput.value += ' ' + transcript;
    } else {
      composerInput.value = transcript;
    }
  };

  recognition.onerror = (err) => {
    console.warn('Speech recognition error:', err);
    stopRecording();
  };

  recognition.onend = () => {
    stopRecording();
  };
}

function stopRecording() {
  isRecording = false;
  if (micBtn) {
    micBtn.classList.remove('recording');
    micBtn.title = 'Click to speak';
  }
}

if (micBtn) {
  micBtn.addEventListener('click', () => {
    if (!recognition) {
      showToast('Voice input is not supported in this browser. Try Chrome or Edge.');
      return;
    }
    if (isRecording) {
      recognition.stop();
      stopRecording();
    } else {
      try {
        recognition.start();
      } catch (e) {
        console.warn(e);
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Smooth Streamer (Typewriter Word Queue)
// ---------------------------------------------------------------------------
class SmoothStreamer {
  constructor(onRender, onFinish) {
    this.onRender = onRender;
    this.onFinish = onFinish;
    this.queue = [];
    this.displayedText = '';
    this.isStreaming = true;
    this.startLoop();
  }

  push(text) {
    if (!text) return;
    for (let i = 0; i < text.length; i++) {
      this.queue.push(text[i]);
    }
  }

  finish() {
    this.isStreaming = false;
  }

  startLoop() {
    const tick = () => {
      if (this.queue.length > 0) {
        // Adapt typing pace based on queue backlog
        const take = Math.max(1, Math.min(6, Math.ceil(this.queue.length / 10)));
        for (let i = 0; i < take && this.queue.length > 0; i++) {
          this.displayedText += this.queue.shift();
        }
        this.onRender(this.displayedText, true);
        setTimeout(tick, 16);
      } else if (this.isStreaming) {
        setTimeout(tick, 20);
      } else {
        this.onRender(this.displayedText, false);
        if (this.onFinish) this.onFinish(this.displayedText);
      }
    };
    tick();
  }
}

// ---------------------------------------------------------------------------
// SSE Streaming Consumer
// ---------------------------------------------------------------------------
async function consumeSSEStream(url, options, onChunk, onComplete) {
  const response = await fetchWithDiagnostics(url, options);

  if (!response.ok) {
    const errorText = await safeErrorDetail(response);
    throw new Error(errorText);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data: ')) continue;
      const dataStr = trimmed.slice(6);
      if (!dataStr) continue;

      try {
        const payload = JSON.parse(dataStr);
        if (payload.error) {
          throw new Error(payload.error);
        }
        if (payload.delta) {
          onChunk(payload.delta);
        }
      } catch (err) {
        if (err.message && !err.message.includes('JSON')) {
          throw err;
        }
      }
    }
  }

  // Flush remaining buffer if any
  if (buffer.trim().startsWith('data: ')) {
    try {
      const payload = JSON.parse(buffer.trim().slice(6));
      if (payload.delta) {
        onChunk(payload.delta);
      }
    } catch {}
  }

  if (onComplete) onComplete();
}

// ---------------------------------------------------------------------------
// Sending messages (Streaming)
// ---------------------------------------------------------------------------
function ensureChat(titleSeed) {
  if (currentChatId && chats[currentChatId]) return currentChatId;
  const id = `chat-${Date.now()}`;
  chats[id] = {
    id,
    title: titleSeed.slice(0, 40) + (titleSeed.length > 40 ? '…' : ''),
    timeLabel: 'Just now',
    messages: [],
  };
  currentChatId = id;
  addHistoryEntry(id, chats[id].title);
  return id;
}

async function sendMessage() {
  const text = composerInput.value.trim();
  if (!text && !pendingFile) return;

  showChatView();
  const chatId = ensureChat(text || pendingFile.name);

  if (chats[chatId].messages.length === 0) {
    updateHistoryTitle(chatId, chats[chatId].title);
  }

  const attachedFile = pendingFile;
  pendingFile = null;
  hideFileChip();
  composerInput.value = '';

  renderMessage('user', text || '(uploaded file)', attachedFile ? { attachmentName: attachedFile.name } : {});
  chats[chatId].messages.push({ role: 'user', content: text || `[uploaded file: ${attachedFile?.name}]` });

  renderTyping();
  sendBtn.disabled = true;

  let assistantMessageRow = null;
  let assistantContentDiv = null;

  try {
    let streamer = null;

    const streamPromise = new Promise((resolve, reject) => {
      streamer = new SmoothStreamer(
        (currentText, isLive) => {
          if (!assistantMessageRow) {
            removeTyping();
            assistantMessageRow = document.createElement('div');
            assistantMessageRow.className = 'message-row assistant';
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            assistantContentDiv = document.createElement('div');
            assistantContentDiv.className = 'message-content';
            bubble.appendChild(assistantContentDiv);
            assistantMessageRow.appendChild(bubble);
            messageList.appendChild(assistantMessageRow);
          }

          assistantContentDiv.innerHTML = parseMarkdown(currentText) + (isLive ? '<span class="streaming-cursor"></span>' : '');
          scrollToBottom();
        },
        (finalText) => {
          resolve(finalText);
        }
      );
    });

    if (attachedFile) {
      const formData = new FormData();
      formData.append('file', attachedFile);
      formData.append('message', text || 'Analyze this file and explain the important points.');
      formData.append('chat_id', chatId);

      await consumeSSEStream(
        `${API_BASE}/upload/stream`,
        { method: 'POST', body: formData },
        (delta) => streamer.push(delta),
        () => streamer.finish()
      );
    } else {
      const history = chats[chatId].messages.slice(0, -1);
      await consumeSSEStream(
        `${API_BASE}/chat/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            message: text,
            history,
          }),
        },
        (delta) => streamer.push(delta),
        () => streamer.finish()
      );
    }

    const fullAnswer = await streamPromise;
    removeTyping();
    chats[chatId].messages.push({ role: 'assistant', content: fullAnswer });
  } catch (err) {
    removeTyping();
    if (assistantMessageRow && !assistantContentDiv?.textContent) {
      assistantMessageRow.remove();
    }
    renderMessage('assistant', `Error talking to AI backend: ${err.message}`, { error: true });
  } finally {
    sendBtn.disabled = false;
    scrollToBottom();
  }
}

async function safeErrorDetail(res) {
  try {
    const data = await res.json();
    return data.detail || `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

async function fetchWithDiagnostics(url, options = {}, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s. Check backend server logs.`);
    }
    throw new Error(`Could not connect to ${url}. Is FastAPI running on port 8000?`);
  } finally {
    clearTimeout(timer);
  }
}

if (sendBtn) sendBtn.addEventListener('click', sendMessage);
if (composerInput) {
  composerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

// ---------------------------------------------------------------------------
// Combine & Analyse (Streaming)
// ---------------------------------------------------------------------------
let combineSelection = [];

function openCombineModal() {
  combineSelection = [];
  const ids = Object.keys(chats);

  if (ids.length < 2) {
    combineList.innerHTML =
      '<p class="combine-empty">You need at least two conversations in history before comparing them. ' +
      'Start a couple of chats (or use the demo ones), then open Combine again.</p>';
    combineRun.disabled = true;
  } else {
    combineRun.disabled = true;
    combineList.innerHTML = '';
    ids.forEach((id) => {
      const label = document.createElement('label');
      label.className = 'combine-option';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = id;
      const span = document.createElement('span');
      span.textContent = chats[id].title;
      label.appendChild(input);
      label.appendChild(span);

      input.addEventListener('change', () => {
        if (input.checked) {
          if (combineSelection.length >= 2) {
            input.checked = false;
            return;
          }
          combineSelection.push(id);
        } else {
          combineSelection = combineSelection.filter((x) => x !== id);
        }
        label.classList.toggle('checked', input.checked);
        combineRun.disabled = combineSelection.length !== 2;
      });

      combineList.appendChild(label);
    });
  }

  combineOverlay.hidden = false;
  combineOverlay.classList.add('is-open');
  document.body.classList.add('modal-open');
}

function closeCombineModal() {
  if (combineOverlay) {
    combineOverlay.hidden = true;
    combineOverlay.classList.remove('is-open');
    document.body.classList.remove('modal-open');
  }
  combineSelection = [];
}

if (combineCancel) combineCancel.addEventListener('click', closeCombineModal);
if (combineClose) combineClose.addEventListener('click', closeCombineModal);
if (combineOverlay) {
  combineOverlay.addEventListener('click', (e) => {
    if (e.target === combineOverlay) closeCombineModal();
  });
}

if (combineRun) {
  combineRun.addEventListener('click', async () => {
    if (combineSelection.length !== 2) return;
    const [idA, idB] = combineSelection;
    const chatA = chats[idA];
    const chatB = chats[idB];
    if (!chatA || !chatB) {
      showToast('Selected conversations are no longer available.');
      closeCombineModal();
      return;
    }
    closeCombineModal();

    showChatView();
    const analysisId = ensureChatForAnalysis(chatA.title, chatB.title);
    renderMessage('user', `Compare "${chatA.title}" with "${chatB.title}"`);
    renderTyping();
    sendBtn.disabled = true;

    let assistantMessageRow = null;
    let assistantContentDiv = null;

    try {
      let streamer = null;

      const streamPromise = new Promise((resolve, reject) => {
        streamer = new SmoothStreamer(
          (currentText, isLive) => {
            if (!assistantMessageRow) {
              removeTyping();
              assistantMessageRow = document.createElement('div');
              assistantMessageRow.className = 'message-row assistant';
              const bubble = document.createElement('div');
              bubble.className = 'message-bubble';
              assistantContentDiv = document.createElement('div');
              assistantContentDiv.className = 'message-content';
              bubble.appendChild(assistantContentDiv);
              assistantMessageRow.appendChild(bubble);
              messageList.appendChild(assistantMessageRow);
            }

            assistantContentDiv.innerHTML = parseMarkdown(currentText) + (isLive ? '<span class="streaming-cursor"></span>' : '');
            scrollToBottom();
          },
          (finalText) => {
            resolve(finalText);
          }
        );
      });

      await consumeSSEStream(
        `${API_BASE}/combine-analyze/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_a: chatA.messages,
            chat_b: chatB.messages,
          }),
        },
        (delta) => streamer.push(delta),
        () => streamer.finish()
      );

      const fullAnalysis = await streamPromise;
      removeTyping();
      chats[analysisId].messages.push({ role: 'assistant', content: fullAnalysis });
    } catch (err) {
      removeTyping();
      if (assistantMessageRow && !assistantContentDiv?.textContent) {
        assistantMessageRow.remove();
      }
      renderMessage('assistant', `Combine & Analyse failed: ${err.message}`, { error: true });
    } finally {
      sendBtn.disabled = false;
      scrollToBottom();
    }
  });
}

function ensureChatForAnalysis(titleA, titleB) {
  const id = `chat-${Date.now()}`;
  const title = `Analysis: ${titleA} vs ${titleB}`;
  chats[id] = {
    id,
    title: title.slice(0, 42) + (title.length > 42 ? '…' : ''),
    timeLabel: 'Just now',
    messages: [{ role: 'user', content: `Compare "${titleA}" with "${titleB}"` }],
  };
  currentChatId = id;
  addHistoryEntry(id, chats[id].title);
  return id;
}

// ---------------------------------------------------------------------------
// Settings Modal Logic
// ---------------------------------------------------------------------------
async function openSettingsModal() {
  if (settingsStatusMsg) settingsStatusMsg.hidden = true;

  try {
    const res = await fetch(`${API_BASE}/api/config`);
    if (res.ok) {
      const data = await res.json();
      if (cfgProvider) cfgProvider.value = data.provider || 'gemini';
      updateProviderSections(data.provider || 'gemini');

      if (data.gemini_model) {
        if (['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-flash-lite', 'gemini-3.7-flash', 'gemma-4-31b-it', 'gemini-flash-latest', 'gemini-pro-latest', 'gemini-2.5-flash', 'gemini-1.5-flash'].includes(data.gemini_model)) {
          cfgGeminiModel.value = data.gemini_model;
          cfgGeminiModelCustom.hidden = true;
        } else {
          cfgGeminiModel.value = 'custom';
          cfgGeminiModelCustom.value = data.gemini_model;
          cfgGeminiModelCustom.hidden = false;
        }
      }

      if (cfgAiModel) cfgAiModel.value = data.ai_model || '';
      if (cfgAiBaseUrl) cfgAiBaseUrl.value = data.ai_base_url || '';

      if (data.gemini_key_set && cfgGeminiKey && !cfgGeminiKey.value) {
        cfgGeminiKey.placeholder = '•••••••••••••••••••••••• (API Key Set)';
      }
      if (data.ai_key_set && cfgAiKey && !cfgAiKey.value) {
        cfgAiKey.placeholder = '•••••••••••••••••••••••• (API Key Set)';
      }
    }
  } catch (err) {
    console.warn('Could not load current settings:', err);
  }

  settingsOverlay.hidden = false;
  settingsOverlay.classList.add('is-open');
  document.body.classList.add('modal-open');
}

function closeSettingsModal() {
  if (settingsOverlay) {
    settingsOverlay.hidden = true;
    settingsOverlay.classList.remove('is-open');
    document.body.classList.remove('modal-open');
  }
}

function updateProviderSections(provider) {
  if (provider === 'gemini') {
    geminiSection.hidden = false;
    genericSection.hidden = true;
  } else {
    geminiSection.hidden = true;
    genericSection.hidden = false;
  }
}

if (cfgProvider) {
  cfgProvider.addEventListener('change', () => {
    updateProviderSections(cfgProvider.value);
  });
}

if (cfgGeminiModel) {
  cfgGeminiModel.addEventListener('change', () => {
    cfgGeminiModelCustom.hidden = cfgGeminiModel.value !== 'custom';
    if (cfgGeminiModel.value === 'custom') cfgGeminiModelCustom.focus();
  });
}

if (toggleGeminiKeyVis) {
  toggleGeminiKeyVis.addEventListener('click', () => {
    cfgGeminiKey.type = cfgGeminiKey.type === 'password' ? 'text' : 'password';
  });
}

if (toggleAiKeyVis) {
  toggleAiKeyVis.addEventListener('click', () => {
    cfgAiKey.type = cfgAiKey.type === 'password' ? 'text' : 'password';
  });
}

if (settingsBtn) settingsBtn.addEventListener('click', openSettingsModal);
if (quickSettingsBtn) quickSettingsBtn.addEventListener('click', openSettingsModal);
if (modelBadge) modelBadge.addEventListener('click', openSettingsModal);
if (settingsClose) settingsClose.addEventListener('click', closeSettingsModal);
if (settingsCancel) settingsCancel.addEventListener('click', closeSettingsModal);

if (settingsOverlay) {
  settingsOverlay.addEventListener('click', (e) => {
    if (e.target === settingsOverlay) closeSettingsModal();
  });
}

if (settingsSave) {
  settingsSave.addEventListener('click', async (e) => {
    e.preventDefault();
    settingsSave.disabled = true;
    settingsSave.textContent = 'Saving...';

    const provider = cfgProvider.value;
    let geminiModel = cfgGeminiModel.value;
    if (geminiModel === 'custom') {
      geminiModel = cfgGeminiModelCustom.value.trim() || 'gemini-3.6-flash';
    }

    const payload = {
      provider,
      gemini_model: geminiModel,
      ai_model: cfgAiModel ? cfgAiModel.value.trim() : '',
      ai_base_url: cfgAiBaseUrl ? cfgAiBaseUrl.value.trim() : '',
    };

    if (cfgGeminiKey && cfgGeminiKey.value.trim()) {
      payload.gemini_api_key = cfgGeminiKey.value.trim();
    }
    if (cfgAiKey && cfgAiKey.value.trim()) {
      payload.ai_api_key = cfgAiKey.value.trim();
    }

    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(await safeErrorDetail(res));

      const data = await res.json();
      updateModelBadge(data.provider, data.model, data.mode);

      settingsStatusMsg.textContent = `✓ Settings saved! Connected with ${data.provider.toUpperCase()} (${data.model}) in ${data.mode} mode.`;
      settingsStatusMsg.className = 'settings-status-msg success';
      settingsStatusMsg.hidden = false;

      setTimeout(() => {
        closeSettingsModal();
      }, 1200);
    } catch (err) {
      settingsStatusMsg.textContent = `Error saving settings: ${err.message}`;
      settingsStatusMsg.className = 'settings-status-msg error';
      settingsStatusMsg.hidden = false;
    } finally {
      settingsSave.disabled = false;
      settingsSave.textContent = 'Save & Connect';
    }
  });
}

// ---------------------------------------------------------------------------
// Demo history
// ---------------------------------------------------------------------------
function seedDemoChats() {
  if (Object.keys(chats).length > 0) return;

  const demos = [
    {
      id: 'demo-quantum',
      title: 'Explain Quantum Computing',
      timeLabel: '10:30 AM',
      messages: [
        { role: 'user', content: 'Explain quantum computing in simple terms.' },
        {
          role: 'assistant',
          content:
            '**Quantum computing** leverages quantum mechanical phenomena such as **superposition** and **entanglement** to perform computations exponentially faster for specific problems:\n\n' +
            '1. **Qubits vs Bits**: Classical bits are strictly 0 or 1. A qubit can exist in a superposition of both states simultaneously.\n' +
            '2. **Entanglement**: Two qubits can become linked so that the state of one instantly influences the other.\n' +
            '3. **Applications**: Molecular simulation, cryptography, battery material discovery, and high-dimensional optimization.',
        },
      ],
    },
    {
      id: 'demo-python',
      title: 'Python Code Help',
      timeLabel: 'Yesterday',
      messages: [
        { role: 'user', content: 'How do I reverse a list in Python?' },
        {
          role: 'assistant',
          content:
            'Here are the most common and idiomatic ways to reverse a list in Python:\n\n' +
            '```python\n# 1. In-place reverse (modifies original list)\nnumbers = [1, 2, 3, 4, 5]\nnumbers.reverse()\nprint(numbers)  # [5, 4, 3, 2, 1]\n\n# 2. Slice notation (creates a new reversed list)\noriginal = [1, 2, 3, 4, 5]\nreversed_list = original[::-1]\n\n# 3. Built-in reversed() iterator\nfor item in reversed(original):\n    print(item)\n```',
        },
      ],
    },
    {
      id: 'demo-ml',
      title: 'Machine Learning Basics',
      timeLabel: 'Yesterday',
      messages: [
        { role: 'user', content: 'What is the difference between supervised and unsupervised learning?' },
        {
          role: 'assistant',
          content:
            '### Supervised vs Unsupervised Learning\n\n' +
            '- **Supervised Learning**: Model trains on labeled datasets $(X, y)$. It learns mapping from inputs to known ground truths (e.g. classification, regression).\n' +
            '- **Unsupervised Learning**: Model works on unlabeled inputs $(X)$ to uncover latent distributions, clusters, or patterns (e.g. K-Means clustering, PCA).\n' +
            '- **Semi-Supervised**: Combines a small set of labeled data with a large body of unlabeled data to reduce annotation costs.',
        },
      ],
    },
    {
      id: 'demo-aixai',
      title: 'AI vs XAI Comparison',
      timeLabel: '2 days ago',
      messages: [
        { role: 'user', content: 'How is explainable AI different from standard AI?' },
        {
          role: 'assistant',
          content:
            'Standard AI deep models frequently operate as opaque "black boxes".\n\n' +
            '**Explainable AI (XAI)** introduces interpretability mechanisms:\n' +
            '- **Feature Attribution**: SHAP and LIME values to identify which features drove a decision.\n' +
            '- **Counterfactual Explanations**: "What minimum change would produce a different result?"\n' +
            '- **Attention Visualization**: Highlighting salient regions in images or tokens in text.',
        },
      ],
    },
  ];

  if (historyEmpty) historyEmpty.hidden = true;
  demos.slice().reverse().forEach((d) => {
    chats[d.id] = { id: d.id, title: d.title, timeLabel: d.timeLabel, messages: d.messages };
    addHistoryEntry(d.id, d.title, d.timeLabel);
  });
}

seedDemoChats();
