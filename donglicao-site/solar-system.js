// ═══════════════════════════════════════════
// LiMa Nebula System — Solar System Background
// Dynamic solar system visualization for the LiMa 星云控制台
// Center Sun = LiMa core; Orbiting planets = intelligent services
// ═══════════════════════════════════════════
(function() {
  const canvas = document.getElementById('solar-canvas') || document.getElementById('particle-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let W, H, cx, cy, animFrame;
  let time = 0;

  // ─── Resize ───
  function resize() {
    W = canvas.width = window.innerWidth * window.devicePixelRatio;
    H = canvas.height = window.innerHeight * window.devicePixelRatio;
    canvas.style.width = window.innerWidth + 'px';
    canvas.style.height = window.innerHeight + 'px';
    cx = W / 2;
    cy = H / 2;
  }
  resize();
  window.addEventListener('resize', resize, { passive: true });

  // ─── Stars ───
  const stars = [];
  for (let i = 0; i < 300; i++) {
    stars.push({
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 1.5 + 0.3,
      alpha: Math.random() * 0.6 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      twinkleSpeed: 0.3 + Math.random() * 1.5
    });
  }

  // ─── Sun ───
  const sun = {
    baseR: 0, // computed on resize
    glow: 0,
    pulse: 0
  };

  // ─── Planets ───
  // name, color, orbit radius ratio, speed, planet radius, hasRing
  const PLANETS = [
    { name: 'Mercury', color: '168,162,158', orbit: 0.08, speed: 2.5, r: 2.5, hasRing: false },
    { name: 'Venus',   color: '217,186,140', orbit: 0.12, speed: 1.8, r: 3.5, hasRing: false },
    { name: 'Earth',   color: '59,130,246',  orbit: 0.17, speed: 1.5, r: 3.8, hasRing: false },
    { name: 'Mars',    color: '220,80,60',   orbit: 0.23, speed: 1.2, r: 3.0, hasRing: false },
    { name: 'Jupiter', color: '200,160,100', orbit: 0.32, speed: 0.6, r: 7.0, hasRing: false },
    { name: 'Saturn',  color: '190,170,130', orbit: 0.42, speed: 0.45, r: 6.0, hasRing: true, ringColor: '160,140,100' },
    { name: 'Uranus',  color: '100,200,220', orbit: 0.52, speed: 0.3, r: 4.5, hasRing: false },
    { name: 'Neptune', color: '60,100,220',  orbit: 0.62, speed: 0.25, r: 4.2, hasRing: false },
  ];

  const planets = PLANETS.map((cfg, i) => ({
    ...cfg,
    angle: Math.random() * Math.PI * 2,
    orbitR: 0,
    tilt: (Math.random() - 0.5) * 0.2
  }));

  function computeOrbits() {
    const maxOrbit = Math.min(W, H) * 0.45;
    sun.baseR = maxOrbit * 0.04;
    planets.forEach(p => {
      p.orbitR = maxOrbit * p.orbit;
    });
  }
  computeOrbits();
  window.addEventListener('resize', () => { computeOrbits(); }, { passive: true });

  // ─── Comets / Shooting Stars ───
  let comets = [];
  class Comet {
    constructor() {
      const side = Math.random() < 0.5 ? 'left' : 'right';
      this.x = side === 'left' ? -50 : W + 50;
      this.y = Math.random() * H * 0.6;
      this.targetX = side === 'left' ? W + 50 : -50;
      this.targetY = this.y + (Math.random() - 0.5) * 200;
      this.speed = 2 + Math.random() * 3;
      this.progress = 0;
      this.trail = [];
      this.done = false;
      this.color = Math.random() < 0.5 ? '200,220,255' : '255,220,150';
    }
    update() {
      this.trail.push({ x: this.x, y: this.y });
      if (this.trail.length > 20) this.trail.shift();
      const dx = this.targetX - this.x;
      const dy = this.targetY - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 5) { this.done = true; return; }
      this.x += (dx / dist) * this.speed;
      this.y += (dy / dist) * this.speed;
    }
    draw() {
      for (let i = 0; i < this.trail.length - 1; i++) {
        const a = (i / this.trail.length) * 0.6;
        ctx.beginPath();
        ctx.moveTo(this.trail[i].x, this.trail[i].y);
        ctx.lineTo(this.trail[i + 1].x, this.trail[i + 1].y);
        ctx.strokeStyle = `rgba(${this.color}, ${a})`;
        ctx.lineWidth = 2 - (this.trail.length - i) * 0.08;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(this.x, this.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.color}, 0.9)`;
      ctx.fill();
    }
  }

  // ─── Draw ───
  function drawStars() {
    stars.forEach(s => {
      const a = s.alpha * (0.5 + 0.5 * Math.sin(time * s.twinkleSpeed + s.twinkle));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(220,230,255,${a})`;
      ctx.fill();
    });
  }

  function drawOrbits() {
    planets.forEach(p => {
      ctx.beginPath();
      ctx.ellipse(cx, cy, p.orbitR, p.orbitR * 0.3, p.tilt, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,255,255,0.03)`;
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }

  function drawSun() {
    const pulse = Math.sin(time * 1.5) * 0.15 + 0.85;
    const r = sun.baseR * pulse;

    // Outer glow layers
    const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 12);
    g1.addColorStop(0, 'rgba(255,200,80,0.12)');
    g1.addColorStop(0.3, 'rgba(255,160,40,0.05)');
    g1.addColorStop(1, 'rgba(255,120,20,0)');
    ctx.fillStyle = g1;
    ctx.fillRect(cx - r * 12, cy - r * 12, r * 24, r * 24);

    // Inner glow
    const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 4);
    g2.addColorStop(0, 'rgba(255,240,200,0.3)');
    g2.addColorStop(0.5, 'rgba(255,200,80,0.1)');
    g2.addColorStop(1, 'rgba(255,140,20,0)');
    ctx.fillStyle = g2;
    ctx.fillRect(cx - r * 4, cy - r * 4, r * 8, r * 8);

    // Core sun
    const g3 = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    g3.addColorStop(0, 'rgba(255,250,230,0.95)');
    g3.addColorStop(0.4, 'rgba(255,220,100,0.8)');
    g3.addColorStop(0.8, 'rgba(255,160,30,0.4)');
    g3.addColorStop(1, 'rgba(255,100,0,0)');
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = g3;
    ctx.fill();

    // Sun rays (subtle)
    for (let i = 0; i < 8; i++) {
      const rayAngle = time * 0.3 + (i / 8) * Math.PI * 2;
      const rayLen = r * (2 + Math.sin(time * 2 + i) * 0.5);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(rayAngle) * r, cy + Math.sin(rayAngle) * r);
      ctx.lineTo(cx + Math.cos(rayAngle) * rayLen, cy + Math.sin(rayAngle) * rayLen);
      ctx.strokeStyle = `rgba(255,200,60,${0.08 * pulse})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  function drawPlanets() {
    planets.forEach(p => {
      p.angle += p.speed * 0.003;
      const x = cx + Math.cos(p.angle) * p.orbitR;
      const y = cy + Math.sin(p.angle) * p.orbitR * 0.3 + p.tilt * p.orbitR * 0.5;

      // Planet glow
      const glow = ctx.createRadialGradient(x, y, 0, x, y, p.r * 3);
      glow.addColorStop(0, `rgba(${p.color},0.3)`);
      glow.addColorStop(1, `rgba(${p.color},0)`);
      ctx.beginPath();
      ctx.arc(x, y, p.r * 3, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      // Planet body
      ctx.beginPath();
      ctx.arc(x, y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.color},0.85)`;
      ctx.fill();

      // Highlight
      ctx.beginPath();
      ctx.arc(x - p.r * 0.3, y - p.r * 0.3, p.r * 0.3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,0.3)`;
      ctx.fill();

      // Saturn ring
      if (p.hasRing) {
        ctx.beginPath();
        ctx.ellipse(x, y, p.r * 2.5, p.r * 0.6, p.angle * 0.5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${p.ringColor},0.4)`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    });
  }

  function drawComets() {
    if (Math.random() < 0.003) comets.push(new Comet());
    comets.forEach((c, i) => {
      c.update(); c.draw();
      if (c.done) comets.splice(i, 1);
    });
  }

  function animate() {
    ctx.clearRect(0, 0, W, H);
    time += 0.016;

    drawStars();
    drawOrbits();
    drawSun();
    drawPlanets();
    drawComets();

    animFrame = requestAnimationFrame(animate);
  }
  animate();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(animFrame);
    else animate();
  });
})();
