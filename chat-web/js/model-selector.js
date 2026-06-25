/* Model selector for the chat console. */

(function () {
  "use strict";

  const DEFAULT_MODELS = ["lima"];
  const STORAGE_KEY = "lima-model";
  const API = "/v1/models";

  const select = document.getElementById("modelSelect");
  if (!select) return;

  function getStoredModel() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "";
    } catch {
      return "";
    }
  }

  function setStoredModel(model) {
    try {
      localStorage.setItem(STORAGE_KEY, model);
    } catch {}
  }

  function getApiKey() {
    try {
      return localStorage.getItem("lima-api-key") || "";
    } catch {
      return "";
    }
  }

  function populate(models, selected) {
    select.innerHTML = "";
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      if (model === selected) option.selected = true;
      select.appendChild(option);
    });
  }

  async function loadModels() {
    const stored = getStoredModel();
    const key = getApiKey();
    if (!key) {
      populate(DEFAULT_MODELS, stored || DEFAULT_MODELS[0]);
      return;
    }
    try {
      const res = await fetch(API, {
        headers: { Authorization: "Bearer " + key },
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const models = (data.data || [])
        .map((m) => (typeof m === "string" ? m : m.id))
        .filter(Boolean);
      populate(models.length ? models : DEFAULT_MODELS, stored);
    } catch (err) {
      console.warn("load models failed:", err);
      populate(DEFAULT_MODELS, stored || DEFAULT_MODELS[0]);
    }
  }

  select.addEventListener("change", () => {
    setStoredModel(select.value);
  });

  window.getSelectedModel = function () {
    return select.value || getStoredModel() || DEFAULT_MODELS[0];
  };

  loadModels();
})();
