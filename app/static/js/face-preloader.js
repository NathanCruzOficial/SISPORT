// =====================================================================
// face-preloader.js — SISPORT V2
// Pré-carrega o modelo de detecção facial UMA VEZ e mantém em cache.
// Nas próximas visitas, carrega do cache (~instantâneo).
// Carregamento silencioso: sem indicador visual na tela.
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

  let modelLoaded = false;

  // ── Cache dos arquivos do modelo ──────────────────────────────────

  async function cacheModelFiles() {
    if (!("caches" in window)) return;

    try {
      const cache = await caches.open(CACHE_NAME);
      const urls = MODEL_FILES.map(f => MODEL_BASE + f);
      urls.push(FACE_API_SRC);

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

      const elapsed = Math.round(performance.now() - startTime);
      console.log(`[face-preloader] face-api.js ✔ (${elapsed}ms, cache: ${cached})`);

      window._facePreloaderReady = true;
      window.dispatchEvent(new Event("facepreloader:ready"));
      return true;

    } catch (err) {
      console.error("[face-preloader] Erro:", err.message);
      window._facePreloaderReady = false;
      return false;
    }
  }

  // ── Iniciar ───────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", () => {
    preloadModel();
  });

  // ── API pública ───────────────────────────────────────────────────

  window.FacePreloader = {
    isReady: () => modelLoaded,
    reload: () => { modelLoaded = false; return preloadModel(); },
    clearCache: async () => {
      if ("caches" in window) await caches.delete(CACHE_NAME);
      console.log("[face-preloader] Cache limpo.");
    }
  };

})();
