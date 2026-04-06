// =====================================================================
// face-preloader.js — SISPORT V2
// Pré-carrega o modelo de detecção facial UMA VEZ e mantém em cache.
// Nas próximas visitas, carrega do cache (~instantâneo).
// Indicador centralizado no rodapé.
// =====================================================================

(function () {
  "use strict";

  const CACHE_NAME = "sisport-face-models-v1";
  const FACE_API_SRC = "/static/js/face-api.min.js";
  const MODEL_BASE = "/static/models/";
  const MODEL_FILES = [
    "tiny_face_detector_model-weights_manifest.json",
    "tiny_face_detector_model-shard1"
  ];

  const STATUS = {
    LOADING: "loading",
    READY: "ready",
    ERROR: "error"
  };

  let currentStatus = STATUS.LOADING;
  let modelLoaded = false;
  let indicatorEl = null;

  // ── Indicador centralizado no rodapé ──────────────────────────────

  function createIndicator() {
    indicatorEl = document.getElementById("camera-status-indicator");
    if (indicatorEl) { updateIndicator(); return; }

    indicatorEl = document.createElement("div");
    indicatorEl.id = "camera-status-indicator";
    indicatorEl.style.cssText =
      "position:fixed; bottom:12px; left:50%; transform:translateX(-50%); " +
      "z-index:9999; padding:6px 16px; border-radius:20px; font-size:0.75rem; " +
      "font-weight:600; color:#fff; cursor:default; " +
      "backdrop-filter:blur(6px); transition:all 0.3s ease; " +
      "box-shadow:0 2px 8px rgba(0,0,0,0.25); display:flex; " +
      "align-items:center; gap:6px; pointer-events:none;";
    document.body.appendChild(indicatorEl);
    updateIndicator();
  }

  function updateIndicator() {
    if (!indicatorEl) return;

    switch (currentStatus) {
      case STATUS.LOADING:
        indicatorEl.style.backgroundColor = "rgba(108,117,125,0.92)";
        indicatorEl.style.pointerEvents = "none";
        indicatorEl.innerHTML =
          '<span class="spinner-border spinner-border-sm" ' +
          'style="width:12px;height:12px;border-width:2px;"></span>' +
          " Preparando câmera…";
        indicatorEl.style.display = "flex";
        indicatorEl.style.opacity = "1";
        break;

      case STATUS.READY:
        indicatorEl.style.backgroundColor = "rgba(25,135,84,0.92)";
        indicatorEl.style.pointerEvents = "none";
        indicatorEl.innerHTML = "📷 Câmera pronta";
        indicatorEl.style.display = "flex";
        indicatorEl.style.opacity = "1";
        setTimeout(() => {
          if (currentStatus === STATUS.READY && indicatorEl) {
            indicatorEl.style.opacity = "0";
            setTimeout(() => {
              if (indicatorEl) indicatorEl.style.display = "none";
            }, 400);
          }
        }, 4000);
        break;

      case STATUS.ERROR:
        indicatorEl.style.backgroundColor = "rgba(220,53,69,0.92)";
        indicatorEl.style.pointerEvents = "auto";
        indicatorEl.style.cursor = "pointer";
        indicatorEl.innerHTML = "⚠️ Câmera indisponível — toque p/ tentar novamente";
        indicatorEl.style.display = "flex";
        indicatorEl.style.opacity = "1";
        indicatorEl.onclick = () => {
          modelLoaded = false;
          preloadModel();
        };
        break;
    }
  }

  // ── Cache dos arquivos do modelo ──────────────────────────────────

  async function cacheModelFiles() {
    if (!("caches" in window)) return;

    try {
      const cache = await caches.open(CACHE_NAME);
      const urls = MODEL_FILES.map(f => MODEL_BASE + f);
      urls.push(FACE_API_SRC);

      // Só baixa os que ainda não estão em cache
      for (const url of urls) {
        const cached = await cache.match(url);
        if (!cached) {
          console.log("[face-preloader] Cacheando:", url);
          await cache.add(url);
        }
      }
    } catch (e) {
      console.warn("[face-preloader] Cache API indisponível:", e.message);
    }
  }

  async function isModelCached() {
    if (!("caches" in window)) return false;
    try {
      const cache = await caches.open(CACHE_NAME);
      for (const f of MODEL_FILES) {
        const cached = await cache.match(MODEL_BASE + f);
        if (!cached) return false;
      }
      const apiCached = await cache.match(FACE_API_SRC);
      return !!apiCached;
    } catch { return false; }
  }

  // ── Carregar script ───────────────────────────────────────────────

  function loadScript(src) {
    return new Promise((res, rej) => {
      if (document.querySelector(`script[src="${src}"]`)) return res();
      const s = document.createElement("script");
      s.src = src;
      s.onload = res;
      s.onerror = () => rej(new Error("Falha ao carregar: " + src));
      document.head.appendChild(s);
    });
  }

  // ── Pré-carregar modelo ───────────────────────────────────────────

  async function preloadModel() {
    if (modelLoaded) return true;

    currentStatus = STATUS.LOADING;
    updateIndicator();

    const cached = await isModelCached();
    console.log("[face-preloader]", cached ? "Modelo em cache ✔" : "Primeiro carregamento…");

    const startTime = performance.now();

    try {
      // 1) Testa FaceDetector nativo (Chrome/Edge 110+)
      if ("FaceDetector" in window) {
        try {
          const test = new window.FaceDetector({ maxDetectedFaces: 1, fastMode: true });
          if (test) {
            modelLoaded = true;
            currentStatus = STATUS.READY;
            updateIndicator();
            const elapsed = Math.round(performance.now() - startTime);
            console.log(`[face-preloader] Nativo ✔ (${elapsed}ms)`);
            window._facePreloaderReady = true;
            window.dispatchEvent(new Event("facepreloader:ready"));
            return true;
          }
        } catch (_) {}
      }

      // 2) Carrega face-api.js (do cache se disponível)
      await loadScript(FACE_API_SRC);

      // 3) Carrega modelo (do cache se disponível)
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_BASE);

      // 4) Salva em cache pro próximo carregamento
      cacheModelFiles();

      modelLoaded = true;
      currentStatus = STATUS.READY;
      updateIndicator();

      const elapsed = Math.round(performance.now() - startTime);
      console.log(`[face-preloader] face-api.js ✔ (${elapsed}ms, cache: ${cached})`);

      window._facePreloaderReady = true;
      window.dispatchEvent(new Event("facepreloader:ready"));
      return true;

    } catch (err) {
      console.error("[face-preloader] Erro:", err.message);
      currentStatus = STATUS.ERROR;
      updateIndicator();
      window._facePreloaderReady = false;
      return false;
    }
  }

  // ── Iniciar ───────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", () => {
    createIndicator();
    preloadModel();
  });

  // ── API pública ───────────────────────────────────────────────────

  window.FacePreloader = {
    isReady: () => modelLoaded,
    getStatus: () => currentStatus,
    reload: () => { modelLoaded = false; return preloadModel(); },
    clearCache: async () => {
      if ("caches" in window) await caches.delete(CACHE_NAME);
      console.log("[face-preloader] Cache limpo.");
    }
  };

})();
