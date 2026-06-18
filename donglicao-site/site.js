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
