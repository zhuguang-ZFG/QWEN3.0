// ─── GALAXY ROUTING VISUALIZATION ───
// Represents LiMa's 170+ backend routing network as a living galaxy
// Center = routing engine; Orbiting particles = AI backends; Connections = routes

(function() {
  const canvas = document.getElementById('galaxy-canvas');
  if (!canvas) return;
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

  let time = 0;
  let mouseX = -1, mouseY = -1;
  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    mouseX = e.clientX - rect.left;
    mouseY = e.clientY - rect.top;
  });
  canvas.addEventListener('mouseleave', () => { mouseX = -1; mouseY = -1; });

  function drawCore() {
    // Core glow
    const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
    coreGlow.addColorStop(0, 'rgba(59,130,246,0.3)');
    coreGlow.addColorStop(0.5, 'rgba(139,92,246,0.15)');
    coreGlow.addColorStop(1, 'rgba(59,130,246,0)');
    ctx.fillStyle = coreGlow;
    ctx.fillRect(cx - 60, cy - 60, 120, 120);

    // Core ring
    ctx.beginPath();
    ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(59,130,246,0.4)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Core dot
    const corePulse = Math.sin(time * 2) * 0.3 + 0.7;
    ctx.beginPath();
    ctx.arc(cx, cy, 5 * corePulse, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(59,130,246,0.9)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, 12 * corePulse, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(59,130,246,0.2)';
    ctx.fill();

    // Ring orbits
    [0.25, 0.45, 0.65, 0.85].forEach((r, i) => {
      const orbitR = (Math.min(W, H) * 0.38) * r;
      ctx.beginPath();
      ctx.ellipse(cx, cy, orbitR, orbitR * 0.55, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(59,130,246,${0.04 - i * 0.008})`;
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
