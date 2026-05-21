/**
 * LiMa AI Chat Application
 */
const App = (() => {
  'use strict';

  const STORAGE_KEY = 'lima-chat-data';
  const API_ENDPOINT = '/v1/chat/completions';

  const state = {
    conversations: [],
    activeId: null,
    mode: 'fast',
    deepThinking: false,
    isStreaming: false,
    pendingImage: null
  };

  // DOM refs
  const $ = (sel) => document.querySelector(sel);
  const dom = {};

  function cacheDom() {
    dom.sidebar = $('#sidebar');
    dom.overlay = $('#sidebarOverlay');
    dom.hamburger = $('#hamburgerBtn');
    dom.newChatBtn = $('#newChatBtn');
    dom.searchInput = $('#searchInput');
    dom.convList = $('#conversationList');
    dom.chatArea = $('#chatArea');
    dom.welcome = $('#welcomeScreen');
    dom.messages = $('#messages');
    dom.input = $('#chatInput');
    dom.sendBtn = $('#sendBtn');
    dom.attachBtn = $('#attachBtn');
    dom.voiceBtn = $('#voiceBtn');
    dom.fileInput = $('#fileInput');
    dom.imagePreview = $('#imagePreview');
    dom.thinkingBtn = $('#thinkingBtn');
    dom.searchBtn = $('#searchBtn');
    dom.modeTabs = $('#modeTabs');
    dom.headerTitle = $('#headerTitle');
  }

  // --- Storage ---
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.conversations));
    } catch { /* quota exceeded, silently fail */ }
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) state.conversations = JSON.parse(raw);
    } catch { state.conversations = []; }
  }

  // --- Conversation Management ---
  function createConversation() {
    const conv = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now()
    };
    state.conversations.unshift(conv);
    state.activeId = conv.id;
    save();
    renderSidebar();
    renderChat();
    return conv;
  }

  function getActive() {
    return state.conversations.find(c => c.id === state.activeId) || null;
  }

  function switchConversation(id) {
    state.activeId = id;
    renderSidebar();
    renderChat();
    closeSidebar();
  }

  function deleteConversation(id) {
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.activeId === id) {
      state.activeId = state.conversations[0]?.id || null;
    }
    save();
    renderSidebar();
    renderChat();
  }

  function autoTitle(conv) {
    if (conv.messages.length >= 1 && conv.title === '新对话') {
      const first = conv.messages.find(m => m.role === 'user');
      if (first) {
        const text = typeof first.content === 'string' ? first.content : '图片对话';
        conv.title = text.slice(0, 30) + (text.length > 30 ? '...' : '');
      }
    }
  }

  // --- Sidebar Rendering ---
  function groupConversations(filter) {
    const now = Date.now();
    const day = 86400000;
    const groups = { today: [], week: [], month: [], older: [] };
    let list = state.conversations;
    if (filter) {
      const q = filter.toLowerCase();
      list = list.filter(c => c.title.toLowerCase().includes(q));
    }
    for (const c of list) {
      const age = now - c.updatedAt;
      if (age < day) groups.today.push(c);
      else if (age < 7 * day) groups.week.push(c);
      else if (age < 30 * day) groups.month.push(c);
      else groups.older.push(c);
    }
    return groups;
  }

  function renderSidebar() {
    const filter = dom.searchInput?.value || '';
    const groups = groupConversations(filter);
    const labels = { today: '今天', week: '7天内', month: '30天内', older: '更早' };
    let html = '';
    for (const [key, convs] of Object.entries(groups)) {
      if (convs.length === 0) continue;
      html += `<div class="conv-group-label">${labels[key]}</div>`;
      for (const c of convs) {
        const active = c.id === state.activeId ? ' active' : '';
        html += `<div class="conv-item${active}" data-id="${c.id}">
          <span class="conv-item-title">${MarkdownRenderer.escapeHtml(c.title)}</span>
          <button class="conv-item-delete" data-del="${c.id}" title="删除">&times;</button>
        </div>`;
      }
    }
    if (!html) html = '<div style="padding:20px;color:var(--text-muted);text-align:center;font-size:0.85rem;">暂无对话</div>';
    dom.convList.innerHTML = html;
    dom.headerTitle.textContent = getActive()?.title || '新对话';
  }

  // --- Chat Rendering ---
  function renderChat() {
    const conv = getActive();
    if (!conv || conv.messages.length === 0) {
      dom.welcome.style.display = 'flex';
      dom.messages.style.display = 'none';
      dom.messages.innerHTML = '';
      return;
    }
    dom.welcome.style.display = 'none';
    dom.messages.style.display = 'flex';
    let html = '';
    for (const msg of conv.messages) {
      html += renderMessage(msg);
    }
    dom.messages.innerHTML = html;
    scrollToBottom();
  }

  function renderMessage(msg) {
    const isUser = msg.role === 'user';
    const avatar = isUser ? '你' : 'Li';
    let content = '';
    if (isUser && typeof msg.content !== 'string') {
      for (const part of msg.content) {
        if (part.type === 'text') content += `<p>${MarkdownRenderer.escapeHtml(part.text)}</p>`;
        if (part.type === 'image_url') content += `<img src="${part.image_url.url}" alt="uploaded" />`;
      }
    } else {
      content = isUser
        ? `<p>${MarkdownRenderer.escapeHtml(msg.content)}</p>`
        : MarkdownRenderer.render(msg.content);
    }
    return `<div class="message ${msg.role}">
      <div class="msg-avatar">${avatar}</div>
      <div class="msg-content">${content}</div>
    </div>`;
  }

  function appendStreamingMessage() {
    dom.welcome.style.display = 'none';
    dom.messages.style.display = 'flex';
    const div = document.createElement('div');
    div.className = 'message assistant';
    div.id = 'streaming-msg';
    div.innerHTML = `<div class="msg-avatar">Li</div>
      <div class="msg-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
    dom.messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function updateStreamingContent(el, text) {
    const contentEl = el.querySelector('.msg-content');
    contentEl.innerHTML = MarkdownRenderer.renderStreaming(text);
    scrollToBottom();
  }

  function renderThinkingStream(el, thinkText, answerText, isThinking, isDone, startTime) {
    const contentEl = el.querySelector('.msg-content');
    let html = '';
    if (thinkText || isThinking) {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      const statusText = isThinking ? `思考中... ${elapsed}s` : `已深度思考 ${elapsed}s`;
      const openClass = isThinking ? 'open' : '';
      html += `<details class="thinking-block ${openClass}" ${isThinking ? 'open' : ''}>`;
      html += `<summary class="thinking-summary"><span class="thinking-icon">💭</span> ${statusText}</summary>`;
      html += `<div class="thinking-content">${MarkdownRenderer.renderStreaming(thinkText)}</div>`;
      html += `</details>`;
    }
    if (answerText) {
      html += MarkdownRenderer.renderStreaming(answerText);
    } else if (isThinking) {
      html += '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    }
    contentEl.innerHTML = html;
    scrollToBottom();
  }

  function scrollToBottom() {
    dom.chatArea.scrollTop = dom.chatArea.scrollHeight;
  }

  // --- API ---
  async function sendMessage(userContent) {
    if (state.isStreaming) return;
    let conv = getActive();
    if (!conv) conv = createConversation();

    const userMsg = { role: 'user', content: userContent };
    conv.messages.push(userMsg);
    autoTitle(conv);
    conv.updatedAt = Date.now();
    save();
    renderSidebar();

    // Render user message
    dom.welcome.style.display = 'none';
    dom.messages.style.display = 'flex';
    const userHtml = renderMessage(userMsg);
    dom.messages.insertAdjacentHTML('beforeend', userHtml);
    scrollToBottom();

    // Start streaming
    state.isStreaming = true;
    dom.sendBtn.disabled = true;
    const streamEl = appendStreamingMessage();
    let fullText = '';
    let thinkText = '';
    let answerText = '';
    let inThinking = false;
    let thinkingDone = false;
    let thinkStart = 0;

    try {
      const apiMessages = conv.messages.map(m => ({ role: m.role, content: m.content }));
      const modelMap = { fast: 'lima', thinking: 'lima-thinking', code: 'lima-code' };
      const body = {
        model: modelMap[state.mode] || 'lima',
        messages: apiMessages,
        stream: true
      };
      if (state.webSearch) body.web_search = true;

      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      thinkStart = Date.now();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') break;
          try {
            const json = JSON.parse(data);
            const delta = json.choices?.[0]?.delta?.content;
            if (delta) {
              fullText += delta;
              // Thinking state machine
              if (!thinkingDone) {
                if (fullText.includes('<think>') && !inThinking) {
                  inThinking = true;
                  thinkStart = Date.now();
                }
                if (inThinking && fullText.includes('</think>')) {
                  thinkingDone = true;
                  inThinking = false;
                  const thinkMatch = fullText.match(/<think>([\s\S]*?)<\/think>/);
                  thinkText = thinkMatch ? thinkMatch[1].trim() : '';
                  answerText = fullText.replace(/<think>[\s\S]*?<\/think>\s*/, '');
                } else if (inThinking) {
                  thinkText = fullText.replace('<think>', '').trim();
                }
              } else {
                answerText = fullText.replace(/<think>[\s\S]*?<\/think>\s*/, '');
              }
              renderThinkingStream(streamEl, thinkText, answerText, inThinking, thinkingDone, thinkStart);
            }
          } catch { /* skip malformed chunk */ }
        }
      }
    } catch (err) {
      if (!fullText) {
        streamEl.querySelector('.msg-content').innerHTML =
          `<div class="msg-error">请求失败: ${MarkdownRenderer.escapeHtml(err.message)}</div>`;
      }
    }

    // Finalize
    state.isStreaming = false;
    dom.sendBtn.disabled = false;
    if (fullText) {
      conv.messages.push({ role: 'assistant', content: fullText });
      conv.updatedAt = Date.now();
      save();
      renderThinkingStream(streamEl, thinkText, answerText || fullText, false, thinkingDone, thinkStart);
    }
    streamEl.removeAttribute('id');
  }

  // --- Input Handling ---
  function handleSend() {
    const text = dom.input.value.trim();
    if (!text && !state.pendingImage) return;
    if (state.isStreaming) return;

    let content;
    if (state.pendingImage) {
      content = [];
      if (text) content.push({ type: 'text', text });
      content.push({ type: 'image_url', image_url: { url: state.pendingImage } });
      clearImage();
    } else {
      content = text;
    }

    dom.input.value = '';
    dom.input.style.height = 'auto';
    dom.sendBtn.disabled = true;
    sendMessage(content);
  }

  function autoResize() {
    dom.input.style.height = 'auto';
    dom.input.style.height = Math.min(dom.input.scrollHeight, 200) + 'px';
    dom.sendBtn.disabled = !dom.input.value.trim() && !state.pendingImage;
  }

  function handleImageUpload(file) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      state.pendingImage = e.target.result;
      dom.imagePreview.classList.add('active');
      dom.imagePreview.innerHTML = `<div class="img-wrap"><img src="${e.target.result}" /><button class="remove-img" onclick="App.clearImage()">&times;</button></div>`;
      dom.sendBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  }

  function clearImage() {
    state.pendingImage = null;
    dom.imagePreview.classList.remove('active');
    dom.imagePreview.innerHTML = '';
    dom.fileInput.value = '';
    dom.sendBtn.disabled = !dom.input.value.trim();
  }

  // --- Mobile sidebar ---
  function openSidebar() { dom.sidebar.classList.add('open'); dom.overlay.classList.add('active'); }
  function closeSidebar() { dom.sidebar.classList.remove('open'); dom.overlay.classList.remove('active'); }

  // --- Event Binding ---
  function bindEvents() {
    dom.newChatBtn.addEventListener('click', createConversation);
    dom.hamburger.addEventListener('click', openSidebar);
    dom.overlay.addEventListener('click', closeSidebar);

    dom.sendBtn.addEventListener('click', handleSend);
    dom.input.addEventListener('input', autoResize);
    dom.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    dom.attachBtn.addEventListener('click', () => dom.fileInput.click());
    dom.fileInput.addEventListener('change', (e) => {
      if (e.target.files[0]) handleImageUpload(e.target.files[0]);
    });

    // Voice recognition
    if (dom.voiceBtn) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.interimResults = true;
        recognition.continuous = false;

        recognition.onresult = (e) => {
          const transcript = Array.from(e.results)
            .map(r => r[0].transcript).join('');
          dom.input.value = transcript;
          autoResize();
        };
        recognition.onend = () => {
          dom.voiceBtn.classList.remove('recording');
        };
        recognition.onerror = () => {
          dom.voiceBtn.classList.remove('recording');
        };

        dom.voiceBtn.addEventListener('click', () => {
          if (dom.voiceBtn.classList.contains('recording')) {
            recognition.stop();
          } else {
            dom.voiceBtn.classList.add('recording');
            recognition.start();
          }
        });
      } else {
        dom.voiceBtn.addEventListener('click', () => {
          alert('当前浏览器不支持语音识别，请使用 Chrome');
        });
      }
    }

    dom.thinkingBtn?.addEventListener('click', () => {
      state.deepThinking = !state.deepThinking;
      if (dom.thinkingBtn) dom.thinkingBtn.dataset.active = state.deepThinking;
    });
    dom.searchBtn?.addEventListener('click', () => {
      state.webSearch = !state.webSearch;
      if (dom.searchBtn) dom.searchBtn.dataset.active = state.webSearch;
    });

    dom.modeTabs?.addEventListener('click', (e) => {
      const tab = e.target.closest('.mode-tab');
      if (!tab) return;
      dom.modeTabs.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.mode = tab.dataset.mode;
    });

    dom.convList.addEventListener('click', (e) => {
      const delBtn = e.target.closest('[data-del]');
      if (delBtn) {
        e.stopPropagation();
        deleteConversation(delBtn.dataset.del);
        return;
      }
      const item = e.target.closest('.conv-item');
      if (item) switchConversation(item.dataset.id);
    });

    dom.searchInput.addEventListener('input', renderSidebar);

    // Export button
    const exportBtn = $('#exportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportConversation);
    }
  }

  // --- Export ---
  function exportConversation() {
    const conv = getActive();
    if (!conv || conv.messages.length === 0) return;
    let md = `# ${conv.title}\n> 导出时间: ${new Date().toLocaleString('zh-CN')}\n\n`;
    for (const m of conv.messages) {
      const role = m.role === 'user' ? '## 👤 User' : '## 🤖 Assistant';
      const text = typeof m.content === 'string' ? m.content : '[图片消息]';
      md += `${role}\n\n${text}\n\n---\n\n`;
    }
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${conv.title.replace(/[^\w一-鿿]/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // --- Init ---
  function init() {
    cacheDom();
    load();
    if (state.conversations.length > 0) {
      state.activeId = state.conversations[0].id;
    }
    renderSidebar();
    renderChat();
    bindEvents();
    dom.input.focus();
  }

  document.addEventListener('DOMContentLoaded', init);

  return { clearImage, exportConversation };
})();
