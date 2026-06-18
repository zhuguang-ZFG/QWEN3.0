// ─── CHAT WEB GALAXY HERO ───
// Compact galaxy visualization for the chat welcome screen
// Replaces the SVG star animation with a living routing network

(function() {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const size = 160 * window.devicePixelRatio;
  canvas.width = size;
  canvas.height = size;
  canvas.style.width = '160px';
  canvas.style.height = '160px';
  const cx = size / 2;
  const cy = size / 2;
  let time = 0, animFrame;

  const nodes = [
    { color: '59,130,246', orbit: 0.35, speed: 0.8, count: 5 },
    { color: '139,92,246', orbit: 0.55, speed: 0.6, count: 4 },
    { color: '52,211,153', orbit: 0.45, speed: 1.0, count: 3 },
    { color: '245,158,11', orbit: 0.65, speed: 0.5, count: 3 },
    { color: '6,182,212', orbit: 0.25, speed: 1.2, count: 4 },
  ];

  const particles = [];
  nodes.forEach(cat => {
    for (let i = 0; i < cat.count; i++) {
      particles.push({
        angle: Math.random() * Math.PI * 2,
        orbitR: (size * 0.38) * cat.orbit + (Math.random() - 0.5) * 10,
        speed: cat.speed * (0.7 + Math.random() * 0.6) * 0.005,
        r: 1.5 + Math.random() * 1.5,
        alpha: 0.5 + Math.random() * 0.4,
        color: cat.color,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: 0.5 + Math.random() * 1.5
      });
    }
  });

  let shootingStars = [];

  function drawCore() {
    const pulse = Math.sin(time * 2) * 0.3 + 0.7;
    // Core glow
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30 * pulse);
    glow.addColorStop(0, 'rgba(59,130,246,0.25)');
    glow.addColorStop(0.5, 'rgba(139,92,246,0.1)');
    glow.addColorStop(1, 'rgba(59,130,246,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(cx - 30, cy - 30, 60, 60);

    // Core ring
    ctx.beginPath();
    ctx.arc(cx, cy, 8 * pulse, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(59,130,246,${0.4 * pulse})`;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Core dot
    ctx.beginPath();
    ctx.arc(cx, cy, 3.5 * pulse, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(59,130,246,0.9)';
    ctx.fill();
  }

  function drawParticles() {
    particles.forEach(p => {
      p.angle += p.speed;
      const x = cx + Math.cos(p.angle) * p.orbitR;
      const y = cy + Math.sin(p.angle) * p.orbitR * 0.55;
      const pulse = Math.sin(time * p.pulseSpeed + p.pulsePhase) * 0.3 + 0.7;
      const r = p.r * pulse;
      const alpha = p.alpha * pulse;

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.color}, ${alpha})`;
      ctx.fill();

      if (pulse > 0.9) {
        ctx.beginPath();
        ctx.arc(x, y, r * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${alpha * 0.15})`;
        ctx.fill();
      }
    });
  }

  function drawConnections() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        if (particles[i].color !== particles[j].color) continue;
        const a1 = particles[i].angle;
        const a2 = particles[j].angle;
        const x1 = cx + Math.cos(a1) * particles[i].orbitR;
        const y1 = cy + Math.sin(a1) * particles[i].orbitR * 0.55;
        const x2 = cx + Math.cos(a2) * particles[j].orbitR;
        const y2 = cy + Math.sin(a2) * particles[j].orbitR * 0.55;
        const dx = x1 - x2;
        const dy = y1 - y2;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 35) {
          const alpha = (1 - dist / 35) * 0.1;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(${particles[i].color}, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
      }
    }
  }

  function drawOrbits() {
    [0.25, 0.45, 0.65].forEach((r, i) => {
      const orbitR = (size * 0.38) * r;
      ctx.beginPath();
      ctx.ellipse(cx, cy, orbitR, orbitR * 0.55, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(59,130,246,${0.05 - i * 0.015})`;
      ctx.lineWidth = 0.5;
      ctx.stroke();
    });
  }

  class ShootingStar {
    constructor() {
      const cat = nodes[Math.floor(Math.random() * nodes.length)];
      const angle = Math.random() * Math.PI * 2;
      const orbitR = (size * 0.38) * cat.orbit;
      this.targetX = cx + Math.cos(angle) * orbitR;
      this.targetY = cy + Math.sin(angle) * orbitR * 0.55;
      this.x = cx; this.y = cy;
      this.progress = 0;
      this.speed = 0.02 + Math.random() * 0.03;
      this.color = cat.color;
      this.trail = [];
      this.returning = false;
      this.done = false;
    }
    update() {
      if (!this.returning) {
        this.progress += this.speed;
        this.trail.push({ x: this.x, y: this.y });
        if (this.trail.length > 12) this.trail.shift();
        this.x = cx + (this.targetX - cx) * this.progress;
        this.y = cy + (this.targetY - cy) * this.progress;
        if (this.progress >= 1) { this.returning = true; this.trail = []; }
      } else {
        this.progress += this.speed * 0.8;
        this.trail.push({ x: this.x, y: this.y });
        if (this.trail.length > 12) this.trail.shift();
        this.x = this.targetX + (cx - this.targetX) * (this.progress - 1);
        this.y = this.targetY + (cy - this.targetY) * (this.progress - 1);
        if (this.progress >= 2) this.done = true;
      }
    }
    draw() {
      // Trail
      for (let i = 0; i < this.trail.length - 1; i++) {
        const t = this.trail[i];
        const next = this.trail[i + 1];
        const alpha = (i / this.trail.length) * 0.5;
        ctx.beginPath();
        ctx.moveTo(t.x, t.y);
        ctx.lineTo(next.x, next.y);
        ctx.strokeStyle = `rgba(${this.color}, ${alpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      // Head
      ctx.beginPath();
      ctx.arc(this.x, this.y, 2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.color}, 0.9)`;
      ctx.fill();
    }
  }

  function animate() {
    ctx.clearRect(0, 0, size, size);
    time += 0.016;

    drawOrbits();
    drawConnections();
    drawCore();
    drawParticles();

    // Shooting stars
    if (Math.random() < 0.03) shootingStars.push(new ShootingStar());
    shootingStars.forEach((s, i) => {
      s.update(); s.draw();
      if (s.done) shootingStars.splice(i, 1);
    });

    animFrame = requestAnimationFrame(animate);
  }
  animate();

  // Pause when hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(animFrame);
    else animate();
  });
})();
