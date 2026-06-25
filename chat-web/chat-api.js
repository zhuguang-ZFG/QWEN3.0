// ─── SEND ───
function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) headers['Authorization'] = 'Bearer ' + key;
  return headers;
}

async function generateImage(prompt) {
  if (isStreaming) return;
  isStreaming = true;
  abortController = new AbortController();
  inputField.value = '';
  inputField.style.height = 'auto';
  setSendLoading(true);

  addMessage('user', '/image ' + prompt);
  messages.push({ role: 'user', content: '/image ' + prompt });
  showTyping('生成图片中...');

  try {
    const response = await fetch('/v1/images/generations', {
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
    const url = json.data && json.data[0] && json.data[0].url;
    if (!url) throw new Error('返回结果中没有图片地址');
    try {
      const u = new URL(url);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') {
        throw new Error('图片地址协议不安全');
      }
    } catch (e) {
      throw new Error('图片地址无效');
    }

    const mediaHtml = `<div class="media-card"><img src="${escapeAttr(url)}" alt="generated image" loading="lazy"></div>`;
    const msg = addMessage('ai', mediaHtml, { model: 'lima-image' });
    msg.querySelector('.msg-bubble').innerHTML = mediaHtml;
    attachImageLightbox(msg.querySelector('.msg-bubble'));
    messages.push({ role: 'assistant', content: url });
    addToHistory('/image ' + prompt);
  } catch (err) {
    hideTyping();
    if (err.name !== 'AbortError') {
      addMessage('ai', `图片生成失败：${err.message}。请检查网络连接或稍后重试。`);
      showToast(`图片生成失败：${err.message}`, { error: true });
    }
  }

  isStreaming = false;
  abortController = null;
  setSendLoading(false);
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
  inputField.value = '';
  inputField.style.height = 'auto';
  setSendLoading(true);

  addMessage('user', text);
  messages.push({ role: 'user', content: text });
  showTyping('思考中');

  try {
    const response = await fetch('/v1/chat/completions', {
      method: 'POST',
      signal: abortController.signal,
      headers: authHeaders(),
      body: JSON.stringify({
        model: window.getSelectedModel ? window.getSelectedModel() : 'lima',
        messages: messages,
        stream: true,
      }),
    });

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

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;

        try {
          const json = JSON.parse(data);
          const delta = json.choices?.[0]?.delta?.content || '';
          if (json.model) modelName = json.model;
          fullText += delta;
          updateLastMessage(fullText);
        } catch (e) {
          console.warn('Failed to parse SSE data line:', data, e);
        }
      }
    }

    if (modelName) {
      const modelTag = chatInner.querySelector('.message.ai:last-of-type .msg-model');
      if (modelTag) modelTag.textContent = modelName;
    }

    finalizeLastMessage();
    messages.push({ role: 'assistant', content: fullText });
    addToHistory(text);

  } catch (err) {
    hideTyping();
    if (err.name !== 'AbortError') {
      addMessage('ai', `请求出错：${err.message}。请检查网络连接或稍后再试。`);
      showToast(`请求出错：${err.message}`, { error: true });
    }
  }

  isStreaming = false;
  abortController = null;
  setSendLoading(false);
}

function sendMessageWithText(text) {
  inputField.value = text;
  sendMessage();
}



// ─── HISTORY ───
function addToHistory(text) {
  const history = document.getElementById('chatHistory');
  const item = document.createElement('div');
  item.className = 'history-item';
  item.textContent = text;
  item.onclick = () => { inputField.value = text; inputField.focus(); };
  history.insertBefore(item, history.firstChild);
  while (history.children.length > 20) {
    history.removeChild(history.lastChild);
  }
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
