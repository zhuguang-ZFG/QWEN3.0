// ─── GALAXY ROUTING VISUALIZATION ───
// Represents LiMa's 170+ backend routing network as a living galaxy
// Center = routing engine; Orbiting particles = AI backends; Connections = routes

(function() {
  const canvas = document.getElementById('galaxy-canvas');
  if (!canvas) return;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', 'LiMa 后端路由星云图，悬停节点可查看模型信息');
  const ctx = canvas.getContext('2d');
  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  let W, H, cx, cy, animFrame;
  let running = false;
  let isIntersecting = false;
  const particles = [];
  const shootingStars = [];

  // Backend categories with their colors
  const CATEGORIES = [
    { name: 'GPT', color: '59,130,246', orbit: 0.35, speed: 0.8, count: 28 },   // Blue - OpenAI/compatible
    { name: 'Claude', color: '139,92,246', orbit: 0.55, speed: 0.6, count: 18 }, // Purple - Anthropic
    { name: 'Groq', color: '52,211,153', orbit: 0.45, speed: 1.2, count: 15 },   // Green - Fast inference
    { name: 'NVIDIA', color: '245,158,11', orbit: 0.65, speed: 0.5, count: 12 },   // Orange - GPU
    { name: 'Local', color: '6,182,212', orbit: 0.25, speed: 1.5, count: 20 },   // Cyan - Local/edge
    { name: 'Image', color: '244,114,182', orbit: 0.75, speed: 0.4, count: 10 },   // Pink - Image gen
    { name: 'Voice', color: '168,85,247', orbit: 0.85, speed: 0.3, count: 8 },    // Violet - Voice
    { name: 'Fallback', color: '148,163,184', orbit: 0.95, speed: 0.2, count: 5 }, // Slate - Fallback
  ];

  const TOTAL_NODES = CATEGORIES.reduce((s, c) => s + c.count, 0);

  const MODELS_BY_CATEGORY = {
    GPT: [
      { name: 'GPT-4o', latency: '300-800ms', price: '中' },
      { name: 'GPT-4o-mini', latency: '200-500ms', price: '低' },
      { name: 'GPT-4-turbo', latency: '300-700ms', price: '中' },
      { name: 'GPT-3.5-turbo', latency: '150-400ms', price: '低' },
      { name: 'o1-preview', latency: '800-2000ms', price: '高' },
    ],
    Claude: [
      { name: 'Claude 3.5 Sonnet', latency: '200-500ms', price: '中' },
      { name: 'Claude 3 Opus', latency: '400-900ms', price: '高' },
      { name: 'Claude 3 Haiku', latency: '150-350ms', price: '低' },
    ],
    Groq: [
      { name: 'Llama 3 70B (Groq)', latency: '50-150ms', price: '免费' },
      { name: 'Mixtral 8x7B (Groq)', latency: '40-120ms', price: '免费' },
      { name: 'Gemma 2 9B (Groq)', latency: '30-100ms', price: '免费' },
    ],
    NVIDIA: [
      { name: 'Nemotron-4', latency: '100-300ms', price: '低' },
      { name: 'Llama 3 70B (NVIDIA)', latency: '120-350ms', price: '低' },
    ],
    Local: [
      { name: 'Qwen2-7B', latency: '80-250ms', price: '低' },
      { name: 'Phi-3-mini', latency: '60-180ms', price: '低' },
      { name: 'Llama 3 8B', latency: '70-200ms', price: '低' },
    ],
    Image: [
      { name: 'DALL·E 3', latency: '2-5s', price: '高' },
      { name: 'Stable Diffusion XL', latency: '1-3s', price: '中' },
      { name: 'Midjourney-proxy', latency: '3-8s', price: '高' },
    ],
    Voice: [
      { name: 'Whisper V3', latency: '300-800ms', price: '中' },
      { name: 'GPT-4o Voice', latency: '400-1000ms', price: '高' },
    ],
    Fallback: [
      { name: 'Cloudflare AI Gateway', latency: '200-600ms', price: '免费' },
    ],
  };

  function pickModel(cat, index) {
    const list = MODELS_BY_CATEGORY[cat.name];
    return list ? list[index % list.length] : { name: cat.name, latency: '-', price: '-' };
  }

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    if (rect.width < 10 || rect.height < 10) return false;
    W = rect.width;
    H = rect.height;
    canvas.width = Math.floor(W * DPR);
    canvas.height = Math.floor(H * DPR);
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    cx = W / 2;
    cy = H / 2;
    return true;
  }

  // Delay initial resize until layout is complete
  function initResize() {
    if (resize()) return;
    requestAnimationFrame(initResize);
  }
  initResize();
  window.addEventListener('resize', resize, { passive: true });

  class Node {
    constructor(category, index) {
      this.cat = category;
      this.angle = Math.random() * Math.PI * 2;
      this.orbitR = (Math.min(W, H) * 0.38) * category.orbit + (Math.random() - 0.5) * 30;
      this.speed = category.speed * (0.7 + Math.random() * 0.6) * 0.003;
      this.r = 1.5 + Math.random() * 2.5;
      this.alpha = 0.4 + Math.random() * 0.5;
      this.pulsePhase = Math.random() * Math.PI * 2;
      this.pulseSpeed = 0.5 + Math.random() * 1.5;
      this.index = index;
      this.hovered = false;
      this.model = pickModel(category, index);
    }
    update(time) {
      this.angle += this.speed;
      this.x = cx + Math.cos(this.angle) * this.orbitR;
      this.y = cy + Math.sin(this.angle) * this.orbitR * 0.55; // Elliptical for 3D feel
      this.pulse = Math.sin(time * this.pulseSpeed + this.pulsePhase) * 0.3 + 0.7;
    }
    draw() {
      const pulseR = this.r * this.pulse * (this.hovered ? 1.8 : 1);
      const alpha = this.alpha * this.pulse * (this.hovered ? 1 : 0.8);
      ctx.beginPath();
      ctx.arc(this.x, this.y, pulseR, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.cat.color}, ${alpha})`;
      ctx.fill();
      // Glow
      if (this.hovered || this.pulse > 0.9) {
        ctx.beginPath();
        ctx.arc(this.x, this.y, pulseR * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${this.cat.color}, ${alpha * 0.15})`;
        ctx.fill();
      }
    }
  }

  class ShootingStar {
    constructor() {
      const cat = CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)];
      const angle = Math.random() * Math.PI * 2;
      const orbitR = (Math.min(W, H) * 0.38) * cat.orbit;
      this.targetX = cx + Math.cos(angle) * orbitR;
      this.targetY = cy + Math.sin(angle) * orbitR * 0.55;
      this.x = cx;
      this.y = cy;
      this.progress = 0;
      this.speed = 0.015 + Math.random() * 0.02;
      this.color = cat.color;
      this.trail = [];
      this.returning = false;
      this.returnProgress = 0;
      this.done = false;
    }
    update() {
      if (!this.returning) {
        this.progress += this.speed;
        this.trail.push({ x: this.x, y: this.y, alpha: 1 });
        if (this.trail.length > 20) this.trail.shift();
        this.x = cx + (this.targetX - cx) * this.progress;
        this.y = cy + (this.targetY - cy) * this.progress;
        if (this.progress >= 1) {
          this.returning = true;
          this.trail = [];
        }
      } else {
        this.returnProgress += this.speed * 0.8;
        this.trail.push({ x: this.x, y: this.y, alpha: 1 });
        if (this.trail.length > 20) this.trail.shift();
        this.x = this.targetX + (cx - this.targetX) * this.returnProgress;
        this.y = this.targetY + (cy - this.targetY) * this.returnProgress;
        if (this.returnProgress >= 1) this.done = true;
      }
      // Fade trail
      this.trail.forEach((t, i) => { t.alpha = i / this.trail.length; });
    }
    draw() {
      // Trail
      this.trail.forEach((t, i) => {
        if (i < this.trail.length - 1) {
          const next = this.trail[i + 1];
          if (!next) return;
          ctx.beginPath();
          ctx.moveTo(t.x, t.y);
          ctx.lineTo(next.x, next.y);
          ctx.strokeStyle = `rgba(${this.color}, ${t.alpha * 0.6})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });
      // Head
      ctx.beginPath();
      ctx.arc(this.x, this.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.color}, 0.9)`;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(this.x, this.y, 8, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.color}, 0.15)`;
      ctx.fill();
    }
  }

  // Initialize nodes
  CATEGORIES.forEach(cat => {
    for (let i = 0; i < cat.count; i++) {
      particles.push(new Node(cat, i));
    }
  });

  const tooltip = document.createElement('div');
  tooltip.id = 'galaxy-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.setAttribute('aria-hidden', 'true');
  document.body.appendChild(tooltip);

  let activeNode = null;
  let touchHideTimer = null;
  let tooltipRect = { width: 0, height: 0 };
  let pendingPos = null;
  let positionRaf = null;

  function findNearest(x, y, radius) {
    let nearest = null;
    let best = radius * radius;
    for (const p of particles) {
      const dx = p.x - x;
      const dy = p.y - y;
      const d2 = dx * dx + dy * dy;
      if (d2 < best) {
        best = d2;
        nearest = p;
      }
    }
    return nearest;
  }

  function updateTooltipRect() {
    const rect = tooltip.getBoundingClientRect();
    tooltipRect.width = rect.width;
    tooltipRect.height = rect.height;
  }

  function positionTooltip(pageX, pageY) {
    const offsetX = 16;
    const offsetY = 16;
    let left = pageX + offsetX;
    let top = pageY + offsetY;
    if (left + tooltipRect.width > window.innerWidth - 8) {
      left = pageX - tooltipRect.width - offsetX;
    }
    if (top + tooltipRect.height > window.innerHeight - 8) {
      top = pageY - tooltipRect.height - offsetY;
    }
    tooltip.style.left = `${left + window.scrollX}px`;
    tooltip.style.top = `${top + window.scrollY}px`;
  }

  function schedulePosition(pageX, pageY) {
    pendingPos = { pageX, pageY };
    if (positionRaf) return;
    positionRaf = requestAnimationFrame(() => {
      positionRaf = null;
      if (pendingPos) positionTooltip(pendingPos.pageX, pendingPos.pageY);
    });
  }

  function showTooltip(node, pageX, pageY) {
    if (!node || !node.model) {
      hideTooltip();
      return;
    }
    if (activeNode !== node) {
      activeNode = node;
      tooltip.textContent = '';
      const strong = document.createElement('strong');
      strong.textContent = node.model.name;
      const span = document.createElement('span');
      span.textContent = `延迟 ${node.model.latency} · 价格 ${node.model.price}`;
      tooltip.appendChild(strong);
      tooltip.appendChild(span);
      tooltip.classList.add('visible');
      tooltip.setAttribute('aria-hidden', 'false');
      updateTooltipRect();
    }
    schedulePosition(pageX, pageY);
  }

  function hideTooltip() {
    activeNode = null;
    tooltip.classList.remove('visible');
    tooltip.setAttribute('aria-hidden', 'true');
    if (positionRaf) {
      cancelAnimationFrame(positionRaf);
      positionRaf = null;
    }
    pendingPos = null;
  }

  let time = 0;
  let mouseX = -1, mouseY = -1;
  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    mouseX = e.clientX - rect.left;
    mouseY = e.clientY - rect.top;
    const node = findNearest(mouseX, mouseY, 20);
    showTooltip(node, e.pageX, e.pageY);
  });
  canvas.addEventListener('mouseleave', () => {
    mouseX = -1;
    mouseY = -1;
    hideTooltip();
  });

  function updateTouch(touch) {
    const rect = canvas.getBoundingClientRect();
    mouseX = touch.clientX - rect.left;
    mouseY = touch.clientY - rect.top;
    const node = findNearest(mouseX, mouseY, 30);
    showTooltip(node, touch.pageX, touch.pageY);
  }

  canvas.addEventListener('touchstart', e => {
    if (e.touches.length) updateTouch(e.touches[0]);
  }, { passive: true });
  canvas.addEventListener('touchmove', e => {
    if (e.touches.length) updateTouch(e.touches[0]);
  }, { passive: true });
  canvas.addEventListener('touchend', () => {
    if (touchHideTimer) clearTimeout(touchHideTimer);
    touchHideTimer = setTimeout(() => {
      mouseX = -1;
      mouseY = -1;
      hideTooltip();
    }, 400);
  });

  function drawCore() {
    // Core glow
    const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 70);
    coreGlow.addColorStop(0, 'rgba(6,182,212,0.35)');
    coreGlow.addColorStop(0.4, 'rgba(139,92,246,0.18)');
    coreGlow.addColorStop(1, 'rgba(6,182,212,0)');
    ctx.fillStyle = coreGlow;
    ctx.fillRect(cx - 70, cy - 70, 140, 140);

    // Core ring
    ctx.beginPath();
    ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(6,182,212,0.5)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Core dot
    const corePulse = Math.sin(time * 2) * 0.3 + 0.7;
    ctx.beginPath();
    ctx.arc(cx, cy, 5 * corePulse, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(6,182,212,0.95)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, 12 * corePulse, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(6,182,212,0.25)';
    ctx.fill();

    // Ring orbits
    [0.25, 0.45, 0.65, 0.85].forEach((r, i) => {
      const orbitR = (Math.min(W, H) * 0.38) * r;
      ctx.beginPath();
      ctx.ellipse(cx, cy, orbitR, orbitR * 0.55, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(6,182,212,${0.05 - i * 0.009})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }

  function drawConnections() {
    // Connect nearby nodes of same category
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        if (particles[i].cat !== particles[j].cat) continue;
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 60) {
          const alpha = (1 - dist / 60) * 0.08;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(${particles[i].cat.color}, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
  }

  function drawLegend() {
    const legendX = 24;
    const legendY = H - 24;
    const lineHeight = 18;
    let y = legendY - (CATEGORIES.length - 1) * lineHeight;

    ctx.font = '11px Inter, system-ui, sans-serif';
    CATEGORIES.forEach((cat, i) => {
      ctx.beginPath();
      ctx.arc(legendX + 4, y + i * lineHeight + 4, 4, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${cat.color}, 0.8)`;
      ctx.fill();
      ctx.fillStyle = 'rgba(148,163,184,0.6)';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${cat.name} · ${cat.count}节点`, legendX + 14, y + i * lineHeight + 4);
    });

    // Total
    ctx.fillStyle = 'rgba(148,163,184,0.4)';
    ctx.font = '10px Inter, system-ui, sans-serif';
    ctx.fillText(`${TOTAL_NODES} 后端节点 · 智能路由`, legendX, y - 10);
  }

  function animate() {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    time += 0.016;

    // Hover detection
    particles.forEach(p => {
      if (mouseX >= 0 && mouseY >= 0) {
        const dx = p.x - mouseX;
        const dy = p.y - mouseY;
        p.hovered = Math.sqrt(dx * dx + dy * dy) < 20;
      } else {
        p.hovered = false;
      }
      p.update(time);
    });

    drawConnections();
    drawCore();

    particles.forEach(p => p.draw());

    // Shooting stars (routing requests)
    if (Math.random() < 0.02) shootingStars.push(new ShootingStar());
    for (let i = shootingStars.length - 1; i >= 0; i--) {
      const s = shootingStars[i];
      s.update();
      s.draw();
      if (s.done) shootingStars.splice(i, 1);
    }

    // Legend
    drawLegend();

    animFrame = requestAnimationFrame(animate);
  }

  function startIfNeeded() {
    if (running || !isIntersecting || document.hidden) return;
    running = true;
    animate();
  }

  function stop() {
    running = false;
    cancelAnimationFrame(animFrame);
    animFrame = null;
  }

  // Intersection observer for performance
  const galaxyObs = new IntersectionObserver(entries => {
    entries.forEach(e => { isIntersecting = e.isIntersecting; });
    if (isIntersecting) startIfNeeded();
    else stop();
  }, { threshold: 0.1 });
  galaxyObs.observe(canvas);

  // Pause when hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
    else startIfNeeded();
  });
})();
