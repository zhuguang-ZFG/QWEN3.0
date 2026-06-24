(() => {
  "use strict";

  // Nav scroll state via IntersectionObserver (no scroll listener)
  const nav = document.getElementById("nav");
  const sentinel = document.querySelector(".scroll-sentinel");

  if (nav && sentinel) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            nav.classList.remove("scrolled");
          } else {
            nav.classList.add("scrolled");
          }
        });
      },
      { threshold: 0, rootMargin: "-30px 0px 0px 0px" }
    );
    navObserver.observe(sentinel);
  }

  // Mobile menu toggle
  const mobileBtn = document.querySelector(".mobile-btn");
  const navLinks = document.querySelector(".nav-links");

  if (mobileBtn && navLinks) {
    mobileBtn.addEventListener("click", () => {
      const open = navLinks.classList.toggle("open");
      mobileBtn.setAttribute("aria-expanded", String(open));
    });

    navLinks.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        navLinks.classList.remove("open");
        mobileBtn.setAttribute("aria-expanded", "false");
      });
    });
  }

  // Scroll reveal via IntersectionObserver
  const revealTargets = [
    ".section-header",
    ".bento-cell",
    ".pipeline-step",
    ".stat",
    ".scenario-card",
    ".testimonial-card",
    ".dev-grid",
    ".galaxy-stage",
    ".galaxy-legend",
    ".faq-item",
    ".contact-inner",
  ];

  const revealEls = document.querySelectorAll(revealTargets.join(","));

  revealEls.forEach((el) => el.classList.add("reveal"));

  // Group staggered children for motion sequencing
  const staggerContainers = [".bento", ".pipeline", ".stats", ".scenario-grid", ".testimonial-grid", ".faq-list"];
  staggerContainers.forEach((selector) => {
    document.querySelectorAll(selector).forEach((container) => {
      container.classList.add("reveal-stagger");
      Array.from(container.children).forEach((child, i) => {
        child.style.setProperty("--i", String(i));
      });
    });
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );

  revealEls.forEach((el) => observer.observe(el));

  // Stats counter animation
  const statValues = document.querySelectorAll(".stat-value");

  const statObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const target = parseInt(el.dataset.target || "0", 10);
        const suffix = el.dataset.suffix || "";
        const duration = 1600;
        const start = performance.now();

        function tick(now) {
          const p = Math.min((now - start) / duration, 1);
          const eased = 1 - Math.pow(1 - p, 4);
          const value = Math.floor(eased * target);
          el.textContent = value + suffix;
          if (p < 1) requestAnimationFrame(tick);
        }

        requestAnimationFrame(tick);
        statObserver.unobserve(el);
      });
    },
    { threshold: 0.5 }
  );

  statValues.forEach((el) => statObserver.observe(el));

  // Code copy button
  const copyBtn = document.querySelector(".code-copy");
  const toast = document.getElementById("copyToast");

  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const codeBody = document.querySelector(".code-body");
      if (!codeBody) return;
      const text = codeBody.innerText;
      try {
        await navigator.clipboard.writeText(text);
        showToast("已复制到剪贴板");
      } catch (err) {
        showToast("复制失败");
      }
    });
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2200);
  }

  // Smooth anchor scrolling offset for fixed nav
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (e) => {
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const y = target.getBoundingClientRect().top + window.scrollY - 90;
      window.scrollTo({ top: y, behavior: "smooth" });
    });
  });
})();
