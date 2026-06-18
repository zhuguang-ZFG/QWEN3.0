// ─── MESSAGES ───
let messageCounter = 0;

function addMessage(role, content, meta) {
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

function formatContent(text) {
  const allowedImageDomains = [
    'image.pollinations.ai',
    'chat.donglicao.com',
    'api.donglicao.com'
  ];
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function escapeAttr(str) {
    // The URL has already been globally HTML-escaped above; only quote-escaping
    // is needed for safe attribute embedding.
    return String(str)
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function isAllowedImageUrl(url) {
    try {
      const u = new URL(url);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
      return allowedImageDomains.some(domain => u.hostname === domain);
    } catch (e) {
      return false;
    }
  }
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, (match, alt, url) => {
      if (!isAllowedImageUrl(url)) {
        return `<a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">[图片: ${escapeHtml(alt || 'image')}]</a>`;
      }
      return `<div class="media-card"><img src="${escapeAttr(url)}" alt="${escapeHtml(alt)}" loading="lazy"></div>`;
    })
    .replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<div class="code-card"><div class="code-header"><div class="code-lights"><span></span><span></span><span></span></div><button class="copy-btn" onclick="copyCode(this)">复制</button></div><pre><code>${code}</code></pre></div>`;
    })
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function attachCodeCopy(root) {
  root.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => copyCode(btn));
  });
}

function copyCode(btn) {
  const code = btn.closest('.code-card').querySelector('code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const original = btn.textContent;
    btn.textContent = '已复制';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 1500);
  }).catch(() => {
    showToast('复制失败，请手动复制', { error: true });
  });
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
