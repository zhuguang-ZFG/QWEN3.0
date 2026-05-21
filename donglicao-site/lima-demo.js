(function() {
  'use strict';

  // --- Styles ---
  const style = document.createElement('style');
  style.textContent = `
    #lima-demo{padding:80px 20px;max-width:1200px;margin:0 auto;font-family:system-ui,-apple-system,sans-serif}
    #lima-demo *{box-sizing:border-box}
    .lima-section-title{text-align:center;font-size:2.2rem;font-weight:700;color:#e2e8f0;margin-bottom:8px}
    .lima-section-sub{text-align:center;color:#94a3b8;font-size:1rem;margin-bottom:48px}
    .lima-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
    @media(max-width:768px){.lima-grid{grid-template-columns:1fr}#lima-demo{padding:48px 16px}.lima-section-title{font-size:1.6rem}}
    .lima-card{background:rgba(26,22,37,0.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-radius:16px;border:1px solid rgba(99,102,241,0.15);padding:24px;opacity:0;transform:translateY(30px);transition:opacity 0.6s ease,transform 0.6s ease}
    .lima-card.lima-visible{opacity:1;transform:translateY(0)}
    .lima-card-title{color:#e2e8f0;font-size:1.1rem;font-weight:600;margin-bottom:16px}
    .lima-input{width:100%;padding:10px 14px;border-radius:10px;border:1px solid rgba(99,102,241,0.3);background:rgba(14,12,21,0.6);color:#e2e8f0;font-size:0.9rem;outline:none;transition:border-color 0.3s}
    .lima-input:focus{border-color:#6366f1}
    .lima-input::placeholder{color:#64748b}
    .lima-btn{padding:10px 20px;border:none;border-radius:10px;background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;font-size:0.9rem;font-weight:600;cursor:pointer;transition:opacity 0.2s,transform 0.1s}
    .lima-btn:hover{opacity:0.9}
    .lima-btn:active{transform:scale(0.97)}
    .lima-btn:disabled{opacity:0.5;cursor:not-allowed}
    .lima-tags{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
    .lima-tag{padding:5px 12px;border-radius:20px;background:rgba(99,102,241,0.15);color:#818cf8;font-size:0.8rem;cursor:pointer;border:1px solid rgba(99,102,241,0.25);transition:background 0.2s}
    .lima-tag:hover{background:rgba(99,102,241,0.3)}
    .lima-row{display:flex;gap:8px;margin-bottom:12px}
    .lima-row .lima-input{flex:1}
    .lima-img-result{width:100%;border-radius:12px;margin-top:12px;cursor:pointer;display:none}
    .lima-img-result.lima-show{display:block}
    .lima-spinner{width:36px;height:36px;border:3px solid rgba(99,102,241,0.2);border-top-color:#6366f1;border-radius:50%;animation:limaSpin 0.8s linear infinite;margin:20px auto;display:none}
    .lima-spinner.lima-show{display:block}
    @keyframes limaSpin{to{transform:rotate(360deg)}}
    .lima-download-btn{display:none;margin-top:8px;padding:6px 14px;border-radius:8px;background:rgba(99,102,241,0.2);color:#818cf8;border:1px solid rgba(99,102,241,0.3);font-size:0.8rem;cursor:pointer}
    .lima-download-btn.lima-show{display:inline-block}
    .lima-chat-box{max-height:300px;overflow-y:auto;margin-bottom:12px;padding:8px;border-radius:10px;background:rgba(14,12,21,0.5)}
    .lima-msg{padding:8px 12px;border-radius:10px;margin-bottom:8px;font-size:0.85rem;line-height:1.5;max-width:85%;word-wrap:break-word}
    .lima-msg-user{background:rgba(59,130,246,0.2);color:#93c5fd;margin-left:auto;text-align:right}
    .lima-msg-ai{background:linear-gradient(135deg,rgba(99,102,241,0.2),rgba(129,140,248,0.15));color:#e2e8f0}
    .lima-chat-footer{text-align:center;font-size:0.7rem;color:#64748b;margin-top:8px}
    .lima-slideshow{position:relative;width:100%;aspect-ratio:16/9;border-radius:12px;overflow:hidden;margin-top:12px;display:none;background:rgba(14,12,21,0.5)}
    .lima-slideshow.lima-show{display:block}
    .lima-slide{position:absolute;inset:0;opacity:0;transition:opacity 1.5s ease}
    .lima-slide.lima-active{opacity:1}
    .lima-slide img{width:100%;height:100%;object-fit:cover}
    .lima-beta-label{position:absolute;top:8px;right:8px;background:rgba(99,102,241,0.8);color:#fff;font-size:0.7rem;padding:2px 8px;border-radius:6px}
    .lima-fullscreen{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;cursor:zoom-out}
    .lima-fullscreen img{max-width:90vw;max-height:90vh;border-radius:8px}
  `;
  document.head.appendChild(style);

  // --- Watermark ---
  function addWatermark(img) {
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.fillRect(0, canvas.height - 40, canvas.width, 40);
    ctx.font = 'bold 16px system-ui, sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.textAlign = 'right';
    ctx.fillText('DongLiCao.com', canvas.width - 16, canvas.height - 14);
    ctx.font = '13px system-ui, sans-serif';
    ctx.fillStyle = 'rgba(149,163,252,0.9)';
    ctx.textAlign = 'left';
    ctx.fillText('Powered by LiMa AI', 16, canvas.height - 14);
    return canvas.toDataURL('image/png');
  }

  // --- Build DOM ---
  const section = document.createElement('section');
  section.id = 'lima-demo';
  section.innerHTML = `
    <h2 class="lima-section-title">体验 AI 能力</h2>
    <p class="lima-section-sub">无需注册，即刻体验 LiMa AI 的多模态能力</p>
    <div class="lima-grid">
      <div class="lima-card" id="lima-card-img">
        <div class="lima-card-title">AI 图片生成</div>
        <div class="lima-row">
          <input class="lima-input" id="lima-img-input" placeholder="描述你想生成的图片...">
          <button class="lima-btn" id="lima-img-btn">生成</button>
        </div>
        <div class="lima-tags">
          <span class="lima-tag" data-p="太空猫">太空猫</span>
          <span class="lima-tag" data-p="赛博朋克">赛博朋克</span>
          <span class="lima-tag" data-p="山水画">山水画</span>
          <span class="lima-tag" data-p="机器人程序员">机器人程序员</span>
        </div>
        <div class="lima-spinner" id="lima-img-spin"></div>
        <img class="lima-img-result" id="lima-img-result" alt="AI生成图片">
        <button class="lima-download-btn" id="lima-img-dl">下载图片</button>
      </div>
      <div class="lima-card" id="lima-card-chat">
        <div class="lima-card-title">AI 对话</div>
        <div class="lima-chat-box" id="lima-chat-box"></div>
        <div class="lima-tags">
          <span class="lima-tag lima-q" data-q="写一个Python排序">写一个Python排序</span>
          <span class="lima-tag lima-q" data-q="解释量子计算">解释量子计算</span>
          <span class="lima-tag lima-q" data-q="翻译成英文">翻译成英文</span>
        </div>
        <div class="lima-row">
          <input class="lima-input" id="lima-chat-input" placeholder="输入你的问题...">
          <button class="lima-btn" id="lima-chat-btn">发送</button>
        </div>
        <div class="lima-chat-footer">Powered by LiMa AI | DongLiCao.com</div>
      </div>
      <div class="lima-card" id="lima-card-video">
        <div class="lima-card-title">AI 动态图像 · Beta</div>
        <div class="lima-row">
          <input class="lima-input" id="lima-vid-input" placeholder="描述视频场景...">
          <button class="lima-btn" id="lima-vid-btn">生成动画</button>
        </div>
        <div class="lima-spinner" id="lima-vid-spin"></div>
        <div class="lima-slideshow" id="lima-slideshow">
          <div class="lima-beta-label">AI 动态图像 · Beta</div>
        </div>
      </div>
    </div>
  `;

  // --- Insert into page ---
  const anchor = document.querySelector('[id="stats"], [id="pricing"], [id="roadmap"]');
  if (anchor) anchor.parentNode.insertBefore(section, anchor);
  else document.body.appendChild(section);

  // --- Intersection Observer ---
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
      if (e.isIntersecting) {
        e.target.classList.add('lima-visible');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });
  section.querySelectorAll('.lima-card').forEach(function(c) { observer.observe(c); });

  // --- Demo 1: Image Generation ---
  const imgInput = document.getElementById('lima-img-input');
  const imgBtn = document.getElementById('lima-img-btn');
  const imgSpin = document.getElementById('lima-img-spin');
  const imgResult = document.getElementById('lima-img-result');
  const imgDl = document.getElementById('lima-img-dl');
  let watermarkedDataUrl = '';

  section.querySelectorAll('#lima-card-img .lima-tag').forEach(function(t) {
    t.addEventListener('click', function() {
      imgInput.value = t.dataset.p;
    });
  });

  function generateImage() {
    const prompt = imgInput.value.trim();
    if (!prompt) return;
    imgBtn.disabled = true;
    imgSpin.classList.add('lima-show');
    imgResult.classList.remove('lima-show');
    imgDl.classList.remove('lima-show');
    const url = 'https://image.pollinations.ai/prompt/' +
      encodeURIComponent(prompt + ', high quality, detailed') +
      '?width=1024&height=1024&nologo=true';
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = function() {
      watermarkedDataUrl = addWatermark(img);
      imgResult.src = watermarkedDataUrl;
      imgResult.classList.add('lima-show');
      imgDl.classList.add('lima-show');
      imgSpin.classList.remove('lima-show');
      imgBtn.disabled = false;
    };
    img.onerror = function() {
      imgSpin.classList.remove('lima-show');
      imgBtn.disabled = false;
    };
    img.src = url;
  }

  imgBtn.addEventListener('click', generateImage);
  imgInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') generateImage(); });

  // Fullscreen view
  imgResult.addEventListener('click', function() {
    const overlay = document.createElement('div');
    overlay.className = 'lima-fullscreen';
    overlay.innerHTML = '<img src="' + watermarkedDataUrl + '" alt="fullscreen">';
    overlay.addEventListener('click', function() { overlay.remove(); });
    document.body.appendChild(overlay);
  });

  // Download
  imgDl.addEventListener('click', function() {
    const a = document.createElement('a');
    a.href = watermarkedDataUrl;
    a.download = 'lima-ai-' + Date.now() + '.png';
    a.click();
  });

  // --- Demo 2: Chat ---
  const chatBox = document.getElementById('lima-chat-box');
  const chatInput = document.getElementById('lima-chat-input');
  const chatBtn = document.getElementById('lima-chat-btn');

  function appendMsg(text, isUser) {
    const div = document.createElement('div');
    div.className = 'lima-msg ' + (isUser ? 'lima-msg-user' : 'lima-msg-ai');
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  section.querySelectorAll('.lima-q').forEach(function(t) {
    t.addEventListener('click', function() {
      chatInput.value = t.dataset.q;
      sendChat();
    });
  });

  function sendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    appendMsg(text, true);
    chatInput.value = '';
    chatBtn.disabled = true;
    fetch('https://api.donglicao.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer sk-lima-demo-2024'
      },
      body: JSON.stringify({
        model: 'lima',
        messages: [{role: 'user', content: text}],
        max_tokens: 200,
        stream: false
      })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var reply = (data.choices && data.choices[0] && data.choices[0].message)
        ? data.choices[0].message.content
        : '抱歉，暂时无法回复，请稍后再试。';
      appendMsg(reply, false);
    })
    .catch(function() {
      appendMsg('网络连接异常，请检查网络后重试。', false);
    })
    .finally(function() { chatBtn.disabled = false; });
  }

  chatBtn.addEventListener('click', sendChat);
  chatInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') sendChat(); });

  // --- Demo 3: Video/Slideshow ---
  const vidInput = document.getElementById('lima-vid-input');
  const vidBtn = document.getElementById('lima-vid-btn');
  const vidSpin = document.getElementById('lima-vid-spin');
  const slideshow = document.getElementById('lima-slideshow');
  let slideInterval = null;

  function generateVideo() {
    const prompt = vidInput.value.trim();
    if (!prompt) return;
    vidBtn.disabled = true;
    vidSpin.classList.add('lima-show');
    slideshow.classList.remove('lima-show');
    if (slideInterval) { clearInterval(slideInterval); slideInterval = null; }
    // Remove old slides
    slideshow.querySelectorAll('.lima-slide').forEach(function(s) { s.remove(); });

    const suffixes = [
      ', establishing shot, cinematic',
      ', medium shot, dramatic lighting',
      ', close up detail, vivid colors',
      ', wide angle, epic scale'
    ];
    let loaded = 0;
    const slides = [];

    suffixes.forEach(function(suffix, i) {
      const url = 'https://image.pollinations.ai/prompt/' +
        encodeURIComponent(prompt + suffix) +
        '?width=1024&height=576&nologo=true&seed=' + (Date.now() + i);
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = function() {
        const wm = addWatermark(img);
        const div = document.createElement('div');
        div.className = 'lima-slide' + (i === 0 ? ' lima-active' : '');
        div.innerHTML = '<img src="' + wm + '" alt="frame ' + (i+1) + '">';
        slides[i] = div;
        loaded++;
        if (loaded === 4) showSlideshow(slides);
      };
      img.onerror = function() {
        loaded++;
        if (loaded === 4) showSlideshow(slides);
      };
      img.src = url;
    });
  }

  function showSlideshow(slides) {
    vidSpin.classList.remove('lima-show');
    vidBtn.disabled = false;
    var validSlides = slides.filter(Boolean);
    if (validSlides.length === 0) return;
    validSlides.forEach(function(s) { slideshow.appendChild(s); });
    slideshow.classList.add('lima-show');
    var current = 0;
    slideInterval = setInterval(function() {
      validSlides[current].classList.remove('lima-active');
      current = (current + 1) % validSlides.length;
      validSlides[current].classList.add('lima-active');
    }, 3000);
  }

  vidBtn.addEventListener('click', generateVideo);
  vidInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') generateVideo(); });

})();
