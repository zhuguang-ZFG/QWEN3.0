// ─── STATE ───
let messages = [];
let isStreaming = false;
let abortController = null;
function getApiKey() {
  return sessionStorage.getItem('lima-api-key') || '';
}

const chatArea = document.getElementById('chatArea');
const chatInner = document.getElementById('chatInner');
const welcomeScreen = document.getElementById('welcomeScreen');
const typingIndicator = document.getElementById('typingIndicator');
const typingText = document.getElementById('typingText');
const inputField = document.getElementById('inputField');
const sendBtn = document.getElementById('sendBtn');
const toastEl = document.getElementById('toast');
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightboxImg');

const placeholderHints = [
  '画一只猫...',
  '写一首七言诗...',
  '/image 一只在星空下弹吉他的猫',
  '帮我画一个生日贺卡...',
  '设备状态怎么样？',
  '用 SVG 画一只小狐狸...'
];
let placeholderIndex = 0;

function cyclePlaceholder() {
  placeholderIndex = (placeholderIndex + 1) % placeholderHints.length;
  inputField.setAttribute('placeholder', placeholderHints[placeholderIndex]);
}
setInterval(cyclePlaceholder, 3200);



// ─── INPUT ───
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 150) + 'px';
  sendBtn.disabled = !el.value.trim() || isStreaming;
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (inputField.value.trim()) handleSendClick();
  }
}

function insertImageCommand() {
  inputField.value = '/image ';
  inputField.focus();
  autoResize(inputField);
}

// ─── VOICE INPUT (Web Speech API) ───
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = document.getElementById('micBtn');
const voiceStatus = document.getElementById('voiceStatus');
if (micBtn && !SpeechRecognition) {
  micBtn.style.display = 'none';
}

let voiceRecognition = null;
let voiceStartTime = 0;
let voiceHoldActive = false;
let voiceFinalTranscript = '';

function setVoiceListening(listening) {
  micBtn?.classList.toggle('listening', listening);
  if (voiceStatus) voiceStatus.hidden = !listening;
}

function startVoiceRecognition() {
  if (!SpeechRecognition || voiceRecognition) return;
  voiceFinalTranscript = '';
  voiceRecognition = new SpeechRecognition();
  voiceRecognition.lang = 'zh-CN';
  voiceRecognition.interimResults = true;
  voiceRecognition.maxAlternatives = 1;

  voiceRecognition.onstart = () => {
    setVoiceListening(true);
  };
  voiceRecognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        voiceFinalTranscript += transcript;
      } else {
        interim += transcript;
      }
    }
    inputField.value = voiceFinalTranscript + interim;
    autoResize(inputField);
  };
  voiceRecognition.onerror = (event) => {
    console.warn('voice recognition error:', event.error);
    if (event.error !== 'aborted' && event.error !== 'no-speech') {
      showToast('语音输入出错：' + event.error, { error: true });
    }
    setVoiceListening(false);
    voiceRecognition = null;
    voiceHoldActive = false;
  };
  voiceRecognition.onend = () => {
    setVoiceListening(false);
    voiceRecognition = null;
    if (voiceHoldActive && inputField.value.trim() && !isStreaming) {
      handleSendClick();
    }
    voiceHoldActive = false;
  };

  try {
    voiceRecognition.start();
  } catch (err) {
    console.warn('voice recognition start failed:', err);
    showToast('无法启动语音输入', { error: true });
    setVoiceListening(false);
    voiceRecognition = null;
    voiceHoldActive = false;
  }
}

function stopVoiceRecognition() {
  if (voiceRecognition) {
    try { voiceRecognition.stop(); } catch {}
  }
}

function onVoicePointerDown(e) {
  if (e.button && e.button !== 0) return;
  e.preventDefault();
  voiceHoldActive = true;
  voiceStartTime = Date.now();
  startVoiceRecognition();
}

function onVoicePointerUp(e) {
  if (!voiceHoldActive) return;
  const held = Date.now() - voiceStartTime;
  if (held < 500) {
    voiceHoldActive = false;
    stopVoiceRecognition();
    inputField.value = '';
    autoResize(inputField);
    showToast('按住时间太短，已取消', { duration: 1500 });
    return;
  }
  stopVoiceRecognition();
}

if (micBtn && SpeechRecognition) {
  micBtn.addEventListener('mousedown', onVoicePointerDown);
  micBtn.addEventListener('touchstart', onVoicePointerDown, { passive: false });
  micBtn.addEventListener('mouseup', onVoicePointerUp);
  micBtn.addEventListener('mouseleave', onVoicePointerUp);
  micBtn.addEventListener('touchend', onVoicePointerUp);
}

function setSendLoading(loading) {
  sendBtn.classList.toggle('loading', loading);
  sendBtn.disabled = loading ? false : !inputField.value.trim();
  sendBtn.setAttribute('aria-label', loading ? '停止生成' : '发送');
}

function handleSendClick() {
  if (isStreaming && abortController) {
    abortController.abort();
    isStreaming = false;
    setSendLoading(false);
    hideTyping();
    return;
  }
  sendMessage();
}



// ─── SIDEBAR ───
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}

document.getElementById('sidebarOverlay').addEventListener('click', toggleSidebar);

function selectDevice(el, name) {
  document.querySelectorAll('.device-card').forEach(d => d.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('topbarTitle').textContent =
    name === 'LiMa AI' ? 'LiMa 星云 AI' : name;
  if (window.innerWidth <= 768) toggleSidebar();
}

function newChat() {
  saveCurrentSession();
  messages = [];
  currentSessionId = null;
  document.querySelectorAll('.message').forEach(m => m.remove());
  welcomeScreen.style.display = 'flex';
  renderSessionList();
  if (window.innerWidth <= 768) toggleSidebar();
}

function sendQuick(text) {
  inputField.value = text;
  sendMessage();
}



// ─── TOAST ───
let toastTimer = null;
function showToast(message, opts = {}) {
  const { duration = 4500, error = false } = opts;
  toastEl.textContent = message;
  toastEl.classList.toggle('error', error);
  toastEl.classList.add('show');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), duration);
}



// ─── LIGHTBOX ───
function openLightbox(src) {
  lightboxImg.src = src;
  lightbox.classList.add('open');
}
function closeLightbox() {
  lightbox.classList.remove('open');
}



// ─── API KEY MODAL ───
let pendingApiKeyCallback = null;

function openApiKeyModal(callback) {
  pendingApiKeyCallback = callback;
  document.getElementById('apiKeyModal').classList.add('open');
  document.getElementById('apiKeyInput').value = sessionStorage.getItem('lima-api-key') || '';
  setTimeout(() => document.getElementById('apiKeyInput').focus(), 50);
}

function closeApiKeyModal() {
  document.getElementById('apiKeyModal').classList.remove('open');
  pendingApiKeyCallback = null;
}

function confirmApiKey() {
  const key = document.getElementById('apiKeyInput').value.trim();
  if (key) {
    sessionStorage.setItem('lima-api-key', key);
  } else {
    sessionStorage.removeItem('lima-api-key');
  }
  closeApiKeyModal();
  if (pendingApiKeyCallback) pendingApiKeyCallback(key);
  else location.reload();
}
