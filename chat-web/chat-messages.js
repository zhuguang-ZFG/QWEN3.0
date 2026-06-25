// ─── MESSAGES ───
let messageCounter = 0;

function renderMessage(role, content, meta) {
  if (welcomeScreen.style.display !== 'none') {
    welcomeScreen.style.display = 'none';
  }

  const msg = document.createElement('div');
  msg.className = `message ${role}`;
  msg.style.animationDelay = `${(messageCounter % 12) * 0.05}s`;
  messageCounter++;

  const avatarIcon = role === 'user'
    ? '<svg class="svg-icon"><use href="#i-user"/></svg>'
    : '<svg class="svg-icon"><use href="#i-bot"/></svg>';
  const modelTag = meta?.model ? `<span class="msg-model">${meta.model}</span>` : '';
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  msg.innerHTML = `
    <div class="msg-avatar ${role}">${avatarIcon}</div>
    <div class="msg-body">
      <div class="msg-bubble">${formatContent(content)}</div>
      <div class="msg-meta">${modelTag}<span>${time}</span></div>
    </div>
  `;

  chatInner.appendChild(msg);
  attachCodeCopy(msg);
  attachImageLightbox(msg);
  scrollToBottom();
  return msg;
}

function addMessage(role, content, meta) {
  const msg = renderMessage(role, content, meta);
  if (role === 'user') {
    highlightAndRender(msg);
  }
  return msg;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  // HTML-attribute context escaping for URL values.
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function isAllowedImageUrl(url) {
  const allowedImageDomains = [
    'image.pollinations.ai',
    'chat.donglicao.com',
    'api.donglicao.com'
  ];
  try {
    const u = new URL(url);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
    return allowedImageDomains.some(domain => u.hostname === domain);
  } catch (e) {
    return false;
  }
}

function formatContent(text) {
  // Extract fenced code blocks first so their content is escaped exactly once.
  const codeBlocks = [];
  let withoutBlocks = String(text || '').replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const key = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push({ lang: lang || 'plaintext', code });
    return key;
  });

  let html = escapeHtml(withoutBlocks)
    .replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, (match, alt, url) => {
      if (!isAllowedImageUrl(url)) {
        return `<a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">[图片: ${escapeHtml(alt || 'image')}]</a>`;
      }
      return `<div class="media-card"><img src="${escapeAttr(url)}" alt="${escapeHtml(alt)}" loading="lazy"></div>`;
    })
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');

  codeBlocks.forEach(({ lang, code }, i) => {
    const key = `__CODE_BLOCK_${i}__`;
    html = html.replace(
      key,
      `<div class="code-card"><div class="code-header"><div class="code-lights"><span></span><span></span><span></span></div><button class="copy-btn" data-action="copy-code">复制</button></div><pre><code class="language-${lang}">${escapeHtml(code)}</code></pre></div>`
    );
  });

  return html;
}

function attachCodeCopy(root) {
  root.querySelectorAll('.copy-btn[data-action="copy-code"]').forEach(btn => {
    btn.addEventListener('click', () => copyCode(btn));
  });
}

function copyCode(btn) {
  const code = btn.closest('.code-card').querySelector('code').textContent;
  const markCopied = () => {
    const original = btn.textContent;
    btn.textContent = '已复制';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 1500);
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(code).then(markCopied).catch((err) => {
      // Fallback for non-secure contexts or denied permission.
      if (tryExecCommandCopy(code)) {
        markCopied();
      } else {
        console.warn('clipboard copy failed:', err);
        showToast('复制失败，请手动复制', { error: true });
      }
    });
  } else if (tryExecCommandCopy(code)) {
    markCopied();
  } else {
    showToast('复制失败，请手动复制', { error: true });
  }
}

function tryExecCommandCopy(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, text.length);
  let success = false;
  try {
    success = document.execCommand('copy');
  } catch (e) {
    success = false;
  }
  document.body.removeChild(textarea);
  return success;
}

function attachImageLightbox(root) {
  root.querySelectorAll('.media-card img').forEach(img => {
    img.addEventListener('click', () => openLightbox(img.src));
  });
}

function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

function showTyping(text) {
  typingText.textContent = text || '思考中';
  typingIndicator.classList.add('active');
  scrollToBottom();
}

function hideTyping() {
  typingIndicator.classList.remove('active');
}

function updateLastMessage(text) {
  const lastMsg = chatInner.querySelector('.message.ai:last-of-type .msg-bubble');
  if (lastMsg) {
    lastMsg.innerHTML = formatContent(text);
    attachCodeCopy(lastMsg.parentElement);
    attachImageLightbox(lastMsg.parentElement);
    scrollToBottom();
  }
}

function highlightAndRender(root) {
  if (window.hljs) {
    root.querySelectorAll('pre code').forEach((el) => {
      try {
        window.hljs.highlightElement(el);
      } catch (e) {
        console.warn('highlight failed:', e);
      }
    });
  }
  if (window.renderMathInElement) {
    try {
      window.renderMathInElement(root, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
        ],
        throwOnError: false,
      });
    } catch (e) {
      console.warn('math render failed:', e);
    }
  }
}

function finalizeLastMessage() {
  const lastMsg = chatInner.querySelector('.message.ai:last-of-type');
  if (lastMsg) {
    highlightAndRender(lastMsg);
  }
}


// ─── SESSIONS ───
let currentSessionId = null;
const SESSIONS_KEY = 'lima_sessions';
const MAX_SESSIONS = 50;

function getSessions() {
  try {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
  } catch {
    return [];
  }
}

function setSessions(sessions) {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
  } catch {}
}

function sessionTitle(msgs) {
  const firstUser = msgs.find((m) => m.role === 'user');
  const text = firstUser ? firstUser.content : '新对话';
  return text.replace(/\s+/g, ' ').trim().slice(0, 40) || '新对话';
}

function saveCurrentSession() {
  if (!messages.length) return;
  const sessions = getSessions();
  const title = sessionTitle(messages);
  const existing = sessions.find((s) => s.id === currentSessionId);
  if (existing) {
    existing.title = title;
    existing.messages = messages.slice();
    existing.model = window.getSelectedModel ? window.getSelectedModel() : 'lima';
    existing.updatedAt = new Date().toISOString();
  } else {
    currentSessionId = currentSessionId || 'sess_' + Date.now();
    sessions.unshift({
      id: currentSessionId,
      title,
      messages: messages.slice(),
      model: window.getSelectedModel ? window.getSelectedModel() : 'lima',
      updatedAt: new Date().toISOString(),
    });
  }
  sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  setSessions(sessions);
  renderSessionList();
}

function renderSessionList() {
  const list = document.getElementById('chatHistory');
  if (!list) return;
  const sessions = getSessions();
  if (!sessions.length) {
    list.innerHTML = '';
    return;
  }
  list.innerHTML = sessions.map((s) => `
    <div class="history-item ${s.id === currentSessionId ? 'active' : ''}" data-session-id="${s.id}">
      <span class="history-title">${escapeHtml(s.title)}</span>
      <button class="history-delete" data-delete-id="${s.id}" aria-label="删除会话">×</button>
    </div>
  `).join('');

  list.querySelectorAll('.history-item').forEach((item) => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.history-delete')) return;
      loadSession(item.dataset.sessionId);
    });
  });
  list.querySelectorAll('.history-delete').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(btn.dataset.deleteId);
    });
  });
}

function loadSession(id) {
  const sessions = getSessions();
  const session = sessions.find((s) => s.id === id);
  if (!session) return;

  saveCurrentSession();
  messages = session.messages.slice();
  currentSessionId = session.id;
  document.querySelectorAll('.message').forEach((m) => m.remove());
  if (messages.length) {
    welcomeScreen.style.display = 'none';
    messages.forEach((m) => {
      const meta = m.role === 'assistant' ? { model: session.model || '...' } : {};
      const el = renderMessage(m.role, m.content, meta);
      if (m.role === 'user') highlightAndRender(el);
    });
    finalizeLastMessage();
  } else {
    welcomeScreen.style.display = 'flex';
  }
  renderSessionList();
  if (window.innerWidth <= 768) toggleSidebar();
}

function deleteSession(id) {
  let sessions = getSessions();
  sessions = sessions.filter((s) => s.id !== id);
  setSessions(sessions);
  if (id === currentSessionId) {
    currentSessionId = null;
    messages = [];
    document.querySelectorAll('.message').forEach((m) => m.remove());
    welcomeScreen.style.display = 'flex';
  }
  renderSessionList();
}

function initSessions() {
  renderSessionList();
}

initSessions();
