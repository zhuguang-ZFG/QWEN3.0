// ═══════════════════════════════════════════
// LiMa Nebula System - Solar System (Dual Mode)
// Full-screen background + mini hero canvas for chat-web
// ═══════════════════════════════════════════
(function() {
  const DPR = Math.min(window.devicePixelRatio || 1, 2);

  // Performance & motion preference scaling.
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches;
  const isMobileViewport = window.innerWidth < 1024;
  const lowMemory = typeof navigator !== 'undefined' && navigator.deviceMemory ? navigator.deviceMemory < 4 : false;
  const lowCores = typeof navigator !== 'undefined' && navigator.hardwareConcurrency ? navigator.hardwareConcurrency < 4 : false;
  const likelyLowEnd = (isCoarsePointer && isMobileViewport) || lowMemory || lowCores;

  // 1 = high, 0.5 = low-end, 0 = reduced-motion.
  const motionScale = prefersReducedMotion ? 0 : (likelyLowEnd ? 0.5 : 1);

  // ─── MODE 1: Full-screen background (solar-canvas) ───
  const bgCanvas = document.getElementById('solar-canvas');
  if (bgCanvas) {
    const bgCtx = bgCanvas.getContext('2d');
    let W, H, cx, cy;
    let bgAnimFrame;
    let bgRunning = true;

    function resizeBg() {
      W = bgCanvas.width = Math.floor(window.innerWidth * DPR);
      H = bgCanvas.height = Math.floor(window.innerHeight * DPR);
      bgCanvas.style.width = window.innerWidth + 'px';
      bgCanvas.style.height = window.innerHeight + 'px';
      cx = W / 2; cy = H / 2;
    }
    resizeBg();
    window.addEventListener('resize', resizeBg, { passive: true });

    // Stars (scaled by performance / motion preference).
    const bgStarCount = Math.floor(200 * motionScale);
    const stars = [];
    for (let i = 0; i < bgStarCount; i++) {
      stars.push({
        x: Math.random() * W, y: Math.random() * H,
        r: Math.random() * 1 + 0.3,
        alpha: Math.random() * 0.5 + 0.2,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.3 + Math.random() * 1.2
      });
    }

    const sunBaseR = 0.04;
    const PLANETS = [
      { color: '6,182,212', orbit: 0.08, speed: 2.5, r: 2.5 },
      { color: '22,211,238', orbit: 0.12, speed: 1.8, r: 3.5 },
      { color: '6,182,212',  orbit: 0.17, speed: 1.5, r: 3.8 },
      { color: '244,114,182',   orbit: 0.23, speed: 1.2, r: 3.0 },
      { color: '34,211,238', orbit: 0.32, speed: 0.6, r: 7.0 },
      { color: '14,165,233', orbit: 0.42, speed: 0.45, r: 6.0, hasRing: true, ringColor: '34,211,238' },
      { color: '22,211,238', orbit: 0.52, speed: 0.3, r: 4.5 },
      { color: '6,182,212',  orbit: 0.62, speed: 0.25, r: 4.2 },
    ];

    const planets = PLANETS.map(cfg => ({
      ...cfg,
      angle: Math.random() * Math.PI * 2,
      orbitR: 0, tilt: (Math.random() - 0.5) * 0.2
    }));

    function computeOrbits() {
      const maxOrbit = Math.min(W, H) * 0.4;
      planets.forEach(p => { p.orbitR = maxOrbit * p.orbit; });
    }
    computeOrbits();
    window.addEventListener('resize', computeOrbits, { passive: true });

    let bgComets = [];
    class BgComet {
      constructor() {
        this.x = Math.random() < 0.5 ? -50 : W + 50;
        this.y = Math.random() * H * 0.6;
        this.targetX = this.x < 0 ? W + 50 : -50;
        this.targetY = this.y + (Math.random() - 0.5) * 200;
        this.speed = 2 + Math.random() * 3;
        this.trail = []; this.done = false;
        this.color = Math.random() < 0.5 ? '200,255,255' : '180,240,255';
      }
      update() {
        this.trail.push({ x: this.x, y: this.y });
        if (this.trail.length > 20) this.trail.shift();
        const dx = this.targetX - this.x, dy = this.targetY - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 5) { this.done = true; return; }
        this.x += (dx / dist) * this.speed;
        this.y += (dy / dist) * this.speed;
      }
      draw() {
        for (let i = 0; i < this.trail.length - 1; i++) {
          const a = (i / this.trail.length) * 0.6;
          bgCtx.beginPath();
          bgCtx.moveTo(this.trail[i].x, this.trail[i].y);
          bgCtx.lineTo(this.trail[i + 1].x, this.trail[i + 1].y);
          bgCtx.strokeStyle = `rgba(${this.color}, ${a})`;
          bgCtx.lineWidth = 2 - (this.trail.length - i) * 0.08;
          bgCtx.stroke();
        }
        bgCtx.beginPath();
        bgCtx.arc(this.x, this.y, 2, 0, Math.PI * 2);
        bgCtx.fillStyle = `rgba(${this.color}, 0.9)`;
        bgCtx.fill();
      }
    }

    let bgTime = 0;
    function bgAnimate() {
      if (!bgRunning) return;
      bgCtx.clearRect(0, 0, W, H);
      bgTime += 0.016;

      // Stars
      stars.forEach(s => {
        const a = s.alpha * (0.5 + 0.5 * Math.sin(bgTime * s.twinkleSpeed + s.twinkle));
        bgCtx.beginPath();
        bgCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        bgCtx.fillStyle = `rgba(200,255,255,${a})`;
        bgCtx.fill();
      });

      // Orbits
      planets.forEach(p => {
        bgCtx.beginPath();
        bgCtx.ellipse(cx, cy, p.orbitR, p.orbitR * 0.3, p.tilt, 0, Math.PI * 2);
        bgCtx.strokeStyle = `rgba(255,255,255,0.03)`;
        bgCtx.lineWidth = 1;
        bgCtx.stroke();
      });

      // Sun
      const sunPulse = Math.sin(bgTime * 1.5) * 0.15 + 0.85;
      const sunR = Math.min(W, H) * sunBaseR * sunPulse;
      const g1 = bgCtx.createRadialGradient(cx, cy, 0, cx, cy, sunR * 12);
      g1.addColorStop(0, 'rgba(180,255,255,0.12)');
      g1.addColorStop(0.3, 'rgba(100,230,255,0.05)');
      g1.addColorStop(1, 'rgba(6,182,212,0)');
      bgCtx.fillStyle = g1;
      bgCtx.fillRect(cx - sunR * 12, cy - sunR * 12, sunR * 24, sunR * 24);
      const g2 = bgCtx.createRadialGradient(cx, cy, 0, cx, cy, sunR * 4);
      g2.addColorStop(0, 'rgba(220,255,255,0.3)');
      g2.addColorStop(0.5, 'rgba(180,255,255,0.1)');
      g2.addColorStop(1, 'rgba(6,182,212,0)');
      bgCtx.fillStyle = g2;
      bgCtx.fillRect(cx - sunR * 4, cy - sunR * 4, sunR * 8, sunR * 8);
      const g3 = bgCtx.createRadialGradient(cx, cy, 0, cx, cy, sunR);
      g3.addColorStop(0, 'rgba(235,255,255,0.95)');
      g3.addColorStop(0.4, 'rgba(150,245,255,0.8)');
      g3.addColorStop(0.8, 'rgba(255,160,30,0.4)');
      g3.addColorStop(1, 'rgba(6,182,212,0)');
      bgCtx.beginPath();
      bgCtx.arc(cx, cy, sunR, 0, Math.PI * 2);
      bgCtx.fillStyle = g3;
      bgCtx.fill();

      // Planets
      planets.forEach(p => {
        p.angle += p.speed * 0.003;
        const x = cx + Math.cos(p.angle) * p.orbitR;
        const y = cy + Math.sin(p.angle) * p.orbitR * 0.3 + p.tilt * p.orbitR * 0.5;
        const glow = bgCtx.createRadialGradient(x, y, 0, x, y, p.r * 3);
        glow.addColorStop(0, `rgba(${p.color},0.3)`);
        glow.addColorStop(1, `rgba(${p.color},0)`);
        bgCtx.beginPath();
        bgCtx.arc(x, y, p.r * 3, 0, Math.PI * 2);
        bgCtx.fillStyle = glow;
        bgCtx.fill();
        bgCtx.beginPath();
        bgCtx.arc(x, y, p.r, 0, Math.PI * 2);
        bgCtx.fillStyle = `rgba(${p.color},0.85)`;
        bgCtx.fill();
        bgCtx.beginPath();
        bgCtx.arc(x - p.r * 0.3, y - p.r * 0.3, p.r * 0.3, 0, Math.PI * 2);
        bgCtx.fillStyle = `rgba(255,255,255,0.3)`;
        bgCtx.fill();
        if (p.hasRing) {
          bgCtx.beginPath();
          bgCtx.ellipse(x, y, p.r * 2.5, p.r * 0.6, p.angle * 0.5, 0, Math.PI * 2);
          bgCtx.strokeStyle = `rgba(${p.ringColor},0.4)`;
          bgCtx.lineWidth = 1.5;
          bgCtx.stroke();
        }
      });

      // Comets
      if (Math.random() < 0.003 * motionScale) bgComets.push(new BgComet());
      for (let i = bgComets.length - 1; i >= 0; i--) {
        const c = bgComets[i];
        c.update(); c.draw();
        if (c.done) bgComets.splice(i, 1);
      }

      if (motionScale > 0) bgAnimFrame = requestAnimationFrame(bgAnimate);
    }
    bgAnimate();
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        bgRunning = false;
        cancelAnimationFrame(bgAnimFrame);
      } else if (!bgRunning) {
        bgRunning = true;
        bgAnimate();
      }
    });
  }

  // ─── MODE 2: Mini hero canvas (heroCanvas) ───
  const heroCanvas = document.getElementById('heroCanvas');
  if (!heroCanvas) return;
  const hCtx = heroCanvas.getContext('2d');
  let hSize = 160 * DPR;
  let hCx = hSize / 2;
  let hCy = hSize / 2;
  let hAnimFrame;
  let hRunning = true;

  function resizeHero() {
    const rect = heroCanvas.parentElement.getBoundingClientRect();
    const cssSize = Math.max(1, Math.floor(Math.min(rect.width, rect.height) || 160));
    hSize = cssSize * DPR;
    heroCanvas.width = hSize;
    heroCanvas.height = hSize;
    heroCanvas.style.width = cssSize + 'px';
    heroCanvas.style.height = cssSize + 'px';
    hCx = hSize / 2;
    hCy = hSize / 2;
    hBodies.forEach(p => { p.orbitR = (hSize * 0.42) * p.orbit; });
  }

  const hPlanets = [
    { color: '6,182,212', orbit: 0.18, speed: 2.5, r: 2.2 },
    { color: '22,211,238', orbit: 0.28, speed: 1.8, r: 2.8 },
    { color: '6,182,212',  orbit: 0.38, speed: 1.5, r: 3.0 },
    { color: '244,114,182',   orbit: 0.50, speed: 1.2, r: 2.5 },
    { color: '34,211,238', orbit: 0.65, speed: 0.6, r: 4.5 },
    { color: '14,165,233', orbit: 0.78, speed: 0.45, r: 3.8, hasRing: true, ringColor: '34,211,238' },
  ];

  const hBodies = hPlanets.map(cfg => ({
    ...cfg,
    angle: Math.random() * Math.PI * 2,
    orbitR: (hSize * 0.42) * cfg.orbit,
    tilt: (Math.random() - 0.5) * 0.15
  }));

  resizeHero();
  window.addEventListener('resize', resizeHero, { passive: true });

  let hComets = [];
  class HComet {
    constructor() {
      this.x = Math.random() < 0.5 ? -20 : hSize + 20;
      this.y = Math.random() * hSize * 0.6;
      this.targetX = this.x < 0 ? hSize + 20 : -20;
      this.targetY = this.y + (Math.random() - 0.5) * 80;
      this.speed = 1.5 + Math.random() * 2;
      this.trail = []; this.done = false;
    }
    update() {
      this.trail.push({ x: this.x, y: this.y });
      if (this.trail.length > 12) this.trail.shift();
      const dx = this.targetX - this.x, dy = this.targetY - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 3) { this.done = true; return; }
      this.x += (dx / dist) * this.speed;
      this.y += (dy / dist) * this.speed;
    }
    draw() {
      for (let i = 0; i < this.trail.length - 1; i++) {
        const a = (i / this.trail.length) * 0.5;
        hCtx.beginPath();
        hCtx.moveTo(this.trail[i].x, this.trail[i].y);
        hCtx.lineTo(this.trail[i + 1].x, this.trail[i + 1].y);
        hCtx.strokeStyle = `rgba(200,255,255,${a})`;
        hCtx.lineWidth = 1.5;
        hCtx.stroke();
      }
      hCtx.beginPath();
      hCtx.arc(this.x, this.y, 1.5, 0, Math.PI * 2);
      hCtx.fillStyle = 'rgba(255,255,255,0.9)';
      hCtx.fill();
    }
  }

  function hDrawSun() {
    const pulse = Math.sin(hTime * 1.5) * 0.15 + 0.85;
    const r = 8 * pulse;
    const g = hCtx.createRadialGradient(hCx, hCy, 0, hCx, hCy, r * 5);
    g.addColorStop(0, 'rgba(150,245,255,0.25)');
    g.addColorStop(0.5, 'rgba(100,230,255,0.1)');
    g.addColorStop(1, 'rgba(6,182,212,0)');
    hCtx.fillStyle = g;
    hCtx.fillRect(hCx - r * 5, hCy - r * 5, r * 10, r * 10);
    const g2 = hCtx.createRadialGradient(hCx, hCy, 0, hCx, hCy, r);
    g2.addColorStop(0, 'rgba(235,255,255,0.95)');
    g2.addColorStop(0.5, 'rgba(150,245,255,0.8)');
    g2.addColorStop(1, 'rgba(255,160,30,0)');
    hCtx.beginPath();
    hCtx.arc(hCx, hCy, r, 0, Math.PI * 2);
    hCtx.fillStyle = g2;
    hCtx.fill();
  }

  function hDrawOrbits() {
    hBodies.forEach(p => {
      hCtx.beginPath();
      hCtx.ellipse(hCx, hCy, p.orbitR, p.orbitR * 0.3, p.tilt, 0, Math.PI * 2);
      hCtx.strokeStyle = 'rgba(255,255,255,0.04)';
      hCtx.lineWidth = 0.5;
      hCtx.stroke();
    });
  }

  function hDrawPlanets() {
    hBodies.forEach(p => {
      p.angle += p.speed * 0.005;
      const x = hCx + Math.cos(p.angle) * p.orbitR;
      const y = hCy + Math.sin(p.angle) * p.orbitR * 0.3 + p.tilt * p.orbitR * 0.5;
      hCtx.beginPath();
      hCtx.arc(x, y, p.r * 2, 0, Math.PI * 2);
      hCtx.fillStyle = `rgba(${p.color},0.2)`;
      hCtx.fill();
      hCtx.beginPath();
      hCtx.arc(x, y, p.r, 0, Math.PI * 2);
      hCtx.fillStyle = `rgba(${p.color},0.85)`;
      hCtx.fill();
      hCtx.beginPath();
      hCtx.arc(x - p.r * 0.3, y - p.r * 0.3, p.r * 0.3, 0, Math.PI * 2);
      hCtx.fillStyle = 'rgba(255,255,255,0.3)';
      hCtx.fill();
      if (p.hasRing) {
        hCtx.beginPath();
        hCtx.ellipse(x, y, p.r * 2.2, p.r * 0.5, p.angle * 0.5, 0, Math.PI * 2);
        hCtx.strokeStyle = `rgba(${p.ringColor},0.4)`;
        hCtx.lineWidth = 1;
        hCtx.stroke();
      }
    });
  }

  function hDrawComets() {
    if (Math.random() < 0.005 * motionScale) hComets.push(new HComet());
    for (let i = hComets.length - 1; i >= 0; i--) {
      const c = hComets[i];
      c.update(); c.draw();
      if (c.done) hComets.splice(i, 1);
    }
  }

  let hTime = 0;
  function hAnimate() {
    if (!hRunning) return;
    hCtx.clearRect(0, 0, hSize, hSize);
    hTime += 0.016;
    hDrawOrbits();
    hDrawSun();
    hDrawPlanets();
    hDrawComets();
    if (motionScale > 0) hAnimFrame = requestAnimationFrame(hAnimate);
  }
  hAnimate();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      hRunning = false;
      cancelAnimationFrame(hAnimFrame);
    } else if (!hRunning) {
      hRunning = true;
      hAnimate();
    }
  });
})();
