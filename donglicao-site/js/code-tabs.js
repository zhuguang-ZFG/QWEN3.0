(() => {
  "use strict";

  function initCodeTabs(container) {
    const tabs = Array.from(container.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;

    const section = container.closest(".dev-code") || container.closest("section");
    const panels = section
      ? Array.from(section.querySelectorAll('.code-panel[role="tabpanel"]'))
      : [];
    const select = section
      ? section.querySelector(".code-tabs-select")
      : null;

    function activate(lang, focusTab = false) {
      const tab = tabs.find((t) => t.dataset.lang === lang);
      if (!tab) return;

      tabs.forEach((t) => {
        const active = t.dataset.lang === lang;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", String(active));
        t.setAttribute("tabindex", active ? "0" : "-1");
      });

      panels.forEach((p) => {
        const active = p.dataset.lang === lang;
        p.hidden = !active;
        p.classList.toggle("active", active);
      });

      if (select) {
        select.value = lang;
      }

      if (focusTab) {
        tab.focus();
      }
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        activate(tab.dataset.lang, false);
      });

      tab.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate(tab.dataset.lang, true);
          return;
        }

        const index = tabs.indexOf(tab);
        let nextIndex = -1;

        if (e.key === "ArrowRight") {
          nextIndex = (index + 1) % tabs.length;
        } else if (e.key === "ArrowLeft") {
          nextIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (e.key === "Home") {
          nextIndex = 0;
        } else if (e.key === "End") {
          nextIndex = tabs.length - 1;
        }

        if (nextIndex !== -1) {
          e.preventDefault();
          activate(tabs[nextIndex].dataset.lang, true);
        }
      });
    });

    if (select) {
      select.addEventListener("change", () => {
        activate(select.value, false);
      });
    }

    // Ensure initial state consistency
    const initial = tabs.find((t) => t.classList.contains("active")) || tabs[0];
    activate(initial.dataset.lang, false);
  }

  document.querySelectorAll('.code-tabs[role="tablist"]').forEach(initCodeTabs);
})();
