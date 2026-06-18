// ─── PARTICLE NETWORK BACKGROUND ───
(function(){
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [], animFrame;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize, { passive: true });

  const COUNT = Math.min(120, Math.floor(W * H / 12000));
  const CONNECTION_DIST = 140;

  class Particle {
    constructor() {
      this.x = Math.random() * W;
      this.y = Math.random() * H;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.r = Math.random() * 1.5 + 0.5;
      this.alpha = Math.random() * 0.4 + 0.2;
      this.color = Math.random() > 0.5 ? '59,130,246' : '139,92,246';
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > W) this.vx *= -1;
      if (this.y < 0 || this.y > H) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.color},${this.alpha})`;
      ctx.fill();
    }
  }

  for (let i = 0; i < COUNT; i++) particles.push(new Particle());

  function drawLines() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONNECTION_DIST) {
          const alpha = (1 - dist / CONNECTION_DIST) * 0.12;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(59,130,246,${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
  }

  let frame = 0;
  function animate() {
    ctx.clearRect(0, 0, W, H);
    // Only draw lines every 2nd frame for performance
    if (frame % 2 === 0) drawLines();
    particles.forEach(p => { p.update(); p.draw(); });
    frame++;
    animFrame = requestAnimationFrame(animate);
  }
  animate();

  // Pause when tab hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(animFrame);
    else animate();
  });
})();

// ─── INTERSECTION OBSERVER ───
const obs = new IntersectionObserver(es => {
  es.forEach((e, i) => {
    if (e.isIntersecting) {
      setTimeout(() => e.target.classList.add('visible'), i * 80);
      obs.unobserve(e.target);
    }
  });
}, { threshold: 0.1 });
document.querySelectorAll('.fade-in').forEach(el => obs.observe(el));

// ─── COUNTER ANIMATION ───
const cObs = new IntersectionObserver(es => {
  es.forEach(e => {
    if (e.isIntersecting) { animateCounters(); cObs.unobserve(e.target); }
  });
}, { threshold: 0.3 });
const sEl = document.querySelector('.stats');
if (sEl) cObs.observe(sEl);

function animateCounters() {
  document.querySelectorAll('.stat-n').forEach(el => {
    const t = parseFloat(el.dataset.target);
    const s = el.dataset.prefix || '';
    const sf = el.dataset.suffix || '';
    const d = 2000;
    const st = performance.now();
    function tick(now) {
      const p = Math.min((now - st) / d, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      el.textContent = s + Math.floor(t * ease) + sf;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}

// ─── SMOOTH SCROLL ───
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const t = document.querySelector(a.getAttribute('href'));
    if (t) t.scrollIntoView({ behavior: 'smooth' });
  });
});

// ─── NAV SCROLL ───
window.addEventListener('scroll', () => {
  document.querySelector('nav').classList.toggle('scrolled', window.scrollY > 50);
}, { passive: true });

// ─── MOBILE MENU ───
const mb = document.querySelector('.mobile-btn'), nl = document.querySelector('.nav-links');
if (mb && nl) {
  mb.addEventListener('click', () => {
    const o = nl.classList.toggle('open');
    mb.setAttribute('aria-expanded', o);
  });
  nl.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    nl.classList.remove('open');
    mb.setAttribute('aria-expanded', 'false');
  }));
}

// ─── COPY CODE ───
const copyBtn = document.querySelector('.code-copy');
if (copyBtn) {
  copyBtn.addEventListener('click', async () => {
    const code = document.querySelector('.code-body');
    if (!code) return;
    const text = code.innerText;
    try { await navigator.clipboard.writeText(text); showToast(); }
    catch {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
      showToast();
    }
  });
}
const toast = document.getElementById('copyToast');
let toastT;
function showToast() {
  if (!toast) return;
  toast.classList.add('show');
  clearTimeout(toastT);
  toastT = setTimeout(() => toast.classList.remove('show'), 1800);
}
