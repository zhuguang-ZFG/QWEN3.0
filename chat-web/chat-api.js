// isAllowedImageUrl / escapeAttr are global lexical bindings declared in
// chat-messages.js (loaded before this script in index.html), sourced from
// js/utils.js (window.LiMaUtils). Do NOT re-declare them here: a top-level
// `var` colliding with an existing global `const` throws SyntaxError and
// prevents this entire file from evaluating.

// ─── SEND ───
function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) headers['Authorization'] = 'Bearer ' + key;
  return headers;
}

// W11: error rendered where it happened, with an in-bubble retry that replays
// the failed user turn (removes the failed bubble + message so nothing dupes).
function renderChatError(message, retryText) {
  // W1: drop skeleton / mid-stream AI bubble so retry does not leave orphans.
  if (typeof removeUnfinalizedAiMessage === 'function') removeUnfinalizedAiMessage();
  // Capture the failed turn now: a later successful send would make
  // "last user" point at the wrong turn if we resolved it at click time.
  const failedUserEl = chatInner.querySelector('.message.user:last-of-type');
  const failedUserMsg =
    messages.length && messages[messages.length - 1].role === 'user'
      ? messages[messages.length - 1]
      : null;
  const msgEl = addMessage('ai', message);
  msgEl.dataset.finalized = '1';
  const bubble = msgEl.querySelector('.msg-bubble');
  if (!bubble || retryText == null) return msgEl;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'msg-retry-btn';
  btn.textContent = '重试';
  btn.addEventListener('click', () => {
    if (isStreaming) return;
    msgEl.remove();
    if (failedUserEl) failedUserEl.remove();
    if (failedUserMsg) {
      const i = messages.indexOf(failedUserMsg);
      if (i !== -1) messages.splice(i, 1);
    }
    sendMessageWithText(retryText);
  });
  bubble.appendChild(document.createElement('div')).appendChild(btn);
  return msgEl;
}

async function generateImage(prompt) {
  if (isStreaming) return;
  isStreaming = true;
  abortController = new AbortController();
  const epoch = streamEpoch;
  inputField.value = '';
  inputField.style.height = 'auto';
  setSendLoading(true);

  addMessage('user', '/image ' + prompt);
  messages.push({ role: 'user', content: '/image ' + prompt });
  showTyping('生成图片中...');

  try {
    const response = await fetch(window.LiMaConfig.getApiUrl('/v1/images/generations', {}), {
      method: 'POST',
      signal: abortController.signal,
      headers: authHeaders(),
      body: JSON.stringify({
        model: 'lima-image',
        prompt: prompt,
        size: '1024x1024',
        n: 1,
      }),
    });

    // Session switch / stop bumped epoch — do not touch the new session's DOM.
    if (epoch !== streamEpoch) return;

    hideTyping();

    if (!response.ok) {
      if (response.status === 401) {
        addMessage('ai', 'API Key 无效或未提供，请点击右上角“Key”按钮设置。');
        isStreaming = false;
        setSendLoading(false);
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const json = await response.json();
    if (epoch !== streamEpoch) return;
    const url = json.data && json.data[0] && json.data[0].url;
    if (!url) throw new Error('返回结果中没有图片地址');
    if (!isAllowedImageUrl(url)) throw new Error('图片地址来源不在白名单');
    try {
      const u = new URL(url);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') {
        throw new Error('图片地址协议不安全');
      }
    } catch (e) {
      throw new Error('图片地址无效');
    }

    // Store markdown so loadSession → formatContent restores the same <img> path.
    const md = `![generated image](${url})`;
    addMessage('ai', md, { model: 'lima-image' });
    // W1: settle the image bubble so a later failed turn's removeUnfinalizedAiMessage()
    // does not treat this successful result as an orphan and delete it.
    finalizeLastMessage();
    messages.push({ role: 'assistant', content: md });
    saveCurrentSession();
  } catch (err) {
    if (epoch !== streamEpoch) return;
    hideTyping();
    if (err.name !== 'AbortError') {
      renderChatError(`图片生成失败：${err.message}。请检查网络连接或稍后重试。`, '/image ' + prompt);
    }
  }

  if (epoch === streamEpoch) {
    isStreaming = false;
    abortController = null;
    setSendLoading(false);
  }
}

async function sendMessage() {
  const text = inputField.value.trim();
  if (!text || isStreaming) return;

  if (text.startsWith('/image ')) {
    const prompt = text.slice(7).trim();
    if (prompt) generateImage(prompt);
    return;
  }

  isStreaming = true;
  abortController = new AbortController();
  const epoch = streamEpoch;
  inputField.value = '';
  inputField.style.height = 'auto';
  setSendLoading(true);

  addMessage('user', text);
  messages.push({ role: 'user', content: text });
  showTyping('思考中');

  const chatBody = {
    model: window.getSelectedModel ? window.getSelectedModel() : 'lima',
    messages: messages,
    stream: true,
  };
  const chatPath = '/v1/chat/completions';
  const pilotAttempt = window.LiMaConfig.shouldUsePilot(chatPath, chatBody);
  const chatOptions = {
    method: 'POST',
    signal: abortController.signal,
    headers: authHeaders(),
    body: JSON.stringify(chatBody),
  };

  async function tryChatFetch(url) {
    return fetch(url, chatOptions);
  }

  async function fallbackIfNeeded(response) {
    const needsFallback = response.status === 429 || response.status === 503 || response.status >= 500;
    if (pilotAttempt && needsFallback) {
      console.warn('Aliyun pilot returned', response.status, '; falling back to primary node');
      return tryChatFetch(window.LiMaConfig.PRIMARY_ORIGIN + chatPath);
    }
    return response;
  }

  try {
    let response;
    try {
      response = await tryChatFetch(window.LiMaConfig.getApiUrl(chatPath, chatBody));
    } catch (err) {
      if (pilotAttempt && err.name !== 'AbortError') {
        console.warn('Aliyun pilot network error;', err.message, '; falling back to primary node');
        response = await tryChatFetch(window.LiMaConfig.PRIMARY_ORIGIN + chatPath);
      } else {
        throw err;
      }
    }
    response = await fallbackIfNeeded(response);
    if (epoch !== streamEpoch) return;

    hideTyping();

    if (!response.ok) {
      if (response.status === 401) {
        addMessage('ai', 'API Key 无效或未提供，请点击右上角“Key”按钮设置。');
        isStreaming = false;
        abortController = null;
        setSendLoading(false);
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let modelName = '';

    addMessage('ai', '', { model: '...' });

    // W10: skeleton lines inside the pending bubble until the first token lands.
    const pendingBubble = chatInner.querySelector('.message.ai:last-of-type .msg-bubble');
    if (pendingBubble) {
      pendingBubble.innerHTML =
        '<div class="skeleton skeleton-text long"></div>' +
        '<div class="skeleton skeleton-text medium"></div>' +
        '<div class="skeleton skeleton-text short"></div>';
    }

    let buffer = '';
    while (true) {
      if (epoch !== streamEpoch) {
        try { reader.cancel(); } catch {}
        return;
      }
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (epoch !== streamEpoch) {
          try { reader.cancel(); } catch {}
          return;
        }
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;

        try {
          const json = JSON.parse(data);
          const delta = json.choices?.[0]?.delta?.content || '';
          if (json.model) modelName = json.model;
          if (delta) {
            fullText += delta;
            updateLastMessage(fullText, { streaming: true });
          }
        } catch (e) {
          console.warn('Failed to parse SSE data line:', data, e);
        }
      }
    }

    if (epoch !== streamEpoch) return;

    if (modelName) {
      const modelTag = chatInner.querySelector('.message.ai:last-of-type .msg-model');
      if (modelTag) modelTag.textContent = modelName;
    }

    // Final render without the streaming caret (also clears the skeleton
    // if the stream produced no tokens at all).
    updateLastMessage(fullText);
    finalizeLastMessage();
    messages.push({ role: 'assistant', content: fullText });
    saveCurrentSession();

  } catch (err) {
    if (epoch !== streamEpoch) return;
    hideTyping();
    if (err.name !== 'AbortError') {
      // W11: network failures and HTTP errors get distinct, actionable copy.
      const isHttpError = /^HTTP \d+/.test(err.message || '');
      const friendly = isHttpError
        ? `服务暂时不可用（${err.message}），请稍后重试。`
        : `网络连接异常（${err.message || '未知错误'}），请检查网络后重试。`;
      renderChatError(friendly, text);
    }
  }

  if (epoch === streamEpoch) {
    isStreaming = false;
    abortController = null;
    setSendLoading(false);
  }
}

function sendMessageWithText(text) {
  inputField.value = text;
  sendMessage();
}



// ─── API INFO ───
function showApiInfo() {
  document.getElementById('apiInfoModal').classList.add('open');
}

function closeApiInfoModal() {
  document.getElementById('apiInfoModal').classList.remove('open');
}

function copyApiInfoCurl() {
  const text = document.getElementById('apiInfoCurl').textContent;
  if (!navigator.clipboard) {
    showToast('复制失败：当前环境不支持剪贴板 API，请手动复制', { error: true });
    return;
  }
  navigator.clipboard.writeText(text).then(() => {
    showToast('curl 命令已复制到剪贴板');
  }).catch(() => {
    showToast('复制失败，请手动复制', { error: true });
  });
}



inputField.focus();
