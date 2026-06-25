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

  function openMenu() {
    navLinks.classList.add("open");
    document.body.classList.add("menu-open");
    mobileBtn.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    navLinks.classList.remove("open");
    document.body.classList.remove("menu-open");
    mobileBtn.setAttribute("aria-expanded", "false");
  }

  function toggleMenu() {
    navLinks.classList.contains("open") ? closeMenu() : openMenu();
  }

  if (mobileBtn && navLinks) {
    mobileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMenu();
    });

    navLinks.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => closeMenu());
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && navLinks.classList.contains("open")) {
        closeMenu();
      }
    });

    document.addEventListener("click", (e) => {
      if (
        navLinks.classList.contains("open") &&
        !navLinks.contains(e.target) &&
        !mobileBtn.contains(e.target)
      ) {
        closeMenu();
      }
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
    ".specs-table-wrap",
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

  // Code copy buttons (bind one handler per .dev-code block)
  const toast = document.getElementById("copyToast");

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2200);
  }

  document.querySelectorAll(".dev-code").forEach((devCode) => {
    const copyBtn = devCode.querySelector(".code-copy");
    if (!copyBtn) return;

    copyBtn.addEventListener("click", async () => {
      const visiblePanel =
        devCode.querySelector('.code-panel:not([hidden])') ||
        devCode.querySelector(".code-panel");
      if (!visiblePanel) return;
      const text = visiblePanel.innerText;
      try {
        await navigator.clipboard.writeText(text);
        showToast("已复制到剪贴板");
      } catch (err) {
        showToast("复制失败");
      }
    });
  });

  // Nav dropdown toggles (desktop hover + mobile click)
  document.querySelectorAll(".nav-dropdown").forEach((dropdown) => {
    const toggle = dropdown.querySelector(".nav-dropdown-toggle");
    if (!toggle) return;
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = dropdown.classList.contains("open");
      document.querySelectorAll(".nav-dropdown").forEach((d) => {
        d.classList.remove("open");
        d.querySelector(".nav-dropdown-toggle")?.setAttribute("aria-expanded", "false");
      });
      dropdown.classList.toggle("open", !isOpen);
      toggle.setAttribute("aria-expanded", String(!isOpen));
    });
  });
  document.addEventListener("click", () => {
    document.querySelectorAll(".nav-dropdown").forEach((d) => {
      d.classList.remove("open");
      d.querySelector(".nav-dropdown-toggle")?.setAttribute("aria-expanded", "false");
    });
  });

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
