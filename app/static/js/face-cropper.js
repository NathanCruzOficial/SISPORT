// =====================================================================
// face-cropper.js — SISPORT V2
// Detecta rosto no stream da câmera e renderiza crop 1:1 centrado
// no rosto com zoom automático. Usa FaceDetector API nativa com
// fallback p/ face-api.js.
//
// API pública:
//   FaceCropper.start(video, canvas, statusCallback) → Promise<bool>
//   FaceCropper.stop()
//   FaceCropper.capture() → string|null (JPEG dataURL)
//   FaceCropper.isActive() → bool
//   FaceCropper.CONFIG.debug = true  → ativa modo debug em tempo real
// =====================================================================

(function () {
  "use strict";

  const LOG = "[face-cropper]";
  function log(...a) { console.log(LOG, ...a); }
  function warn(...a) { console.warn(LOG, ...a); }

  const C = {
    aspectRatio:       1,       // Proporção do crop (1 = quadrado 1:1)
    outputWidth:       480,     // Largura em px do canvas de saída (altura = outputWidth / aspectRatio)
    facePadding:       0.25,    // Margem ao redor do rosto (0.25 = 25% extra de cada lado)
    topBias:           0.40,    // Deslocamento vertical do crop pra cima (maior = menos topo da cabeça)
    marginSafety:      0.08,    // Margem mínima de segurança pra o rosto não encostar na borda (8%)
    detectionInterval: 200,     // Intervalo entre detecções de rosto em ms (menor = mais responsivo, mais CPU)
    smoothing:         0.88,    // Suavização do movimento do crop (0 = instantâneo, 1 = parado)
    minFaceSize:       60,      // Tamanho mínimo em px pra considerar um rosto válido
    debug:             false,   // Modo debug: mostra vídeo original com quadrados verdes nos rostos detectados
    // faceApiCdn:    "https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js",
    // faceApiModels: "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/model/"
    faceApiCdn:    "/static/js/face-api.min.js",
    faceApiModels: "/static/models/",
  };


  let detector     = null;
  let detectorType = "none";
  let animId       = null;
  let detectTimer  = null;
  let crop         = null;
  let lastDet      = null;
  let lastFaces    = [];        // Guarda todos os rostos pra usar no debug
  let running      = false;
  let _video       = null;
  let _canvas      = null;
  let _ctx         = null;
  let _onStatus    = null;

  // -----------------------------------------------------------------
  // Inicialização do detector
  // -----------------------------------------------------------------
  async function initDetector() {
    if ("FaceDetector" in window) {
      try {
        detector = new window.FaceDetector({ maxDetectedFaces: 5, fastMode: true });
        detectorType = "native";
        log("FaceDetector nativo ✔");
        return true;
      } catch (e) { warn("Nativo falhou:", e.message); }
    }

    log("Carregando face-api.js...");
    try {
      await loadScript(C.faceApiCdn);
      await faceapi.nets.tinyFaceDetector.loadFromUri(C.faceApiModels);
      detectorType = "faceapi";
      log("face-api.js ✔");
      return true;
    } catch (e) {
      warn("face-api.js falhou:", e.message);
      detectorType = "none";
      return false;
    }
  }

  function loadScript(src) {
    return new Promise((res, rej) => {
      if (document.querySelector(`script[src="${src}"]`)) return res();
      const s = document.createElement("script");
      s.src = src; s.onload = res;
      s.onerror = () => rej(new Error("Load fail: " + src));
      document.head.appendChild(s);
    });
  }

  // -----------------------------------------------------------------
  // Detecção de rostos — detecta TODOS e retorna o MAIOR
  // -----------------------------------------------------------------
  async function detectFace(v) {
    if (!v || v.readyState < 2) return null;
    try {
      let faces = [];

      if (detectorType === "native") {
        const f = await detector.detect(v);
        if (!f || !f.length) { lastFaces = []; return null; }
        faces = f.map(d => ({
          x: d.boundingBox.x,
          y: d.boundingBox.y,
          w: d.boundingBox.width,
          h: d.boundingBox.height
        }));
      }

      if (detectorType === "faceapi") {
        const results = await faceapi.detectAllFaces(v,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.45 }));
        if (!results || !results.length) { lastFaces = []; return null; }
        faces = results.map(r => ({
          x: r.box.x,
          y: r.box.y,
          w: r.box.width,
          h: r.box.height
        }));
      }

      if (!faces.length) { lastFaces = []; return null; }

      // Filtra rostos menores que o mínimo
      faces = faces.filter(f => f.w >= C.minFaceSize && f.h >= C.minFaceSize);
      if (!faces.length) { lastFaces = []; return null; }

      // Salva todos os rostos pro modo debug
      lastFaces = faces;

      // Retorna o maior rosto (mais próximo da câmera)
      return faces.reduce((a, b) => (a.w * a.h) >= (b.w * b.h) ? a : b);

    } catch (_) {}
    return null;
  }

  // -----------------------------------------------------------------
  // Debug overlay — desenha todos os rostos com quadrados verdes
  // -----------------------------------------------------------------
  function drawDebugOverlay(v, faces) {
    const vw = v.videoWidth;
    const vh = v.videoHeight;

    // Ajusta o canvas pro tamanho real do vídeo
    _canvas.width  = vw;
    _canvas.height = vh;

    // Desenha o vídeo inteiro (sem crop)
    _ctx.drawImage(v, 0, 0, vw, vh);

    // Estilo dos quadrados
    _ctx.strokeStyle = "#00ff00";
    _ctx.lineWidth   = 3;
    _ctx.font        = "bold 14px monospace";
    _ctx.fillStyle   = "#00ff00";

    // Encontra o maior rosto pra destacar
    let biggestIdx = 0;
    let biggestArea = 0;
    faces.forEach((f, i) => {
      const area = f.w * f.h;
      if (area > biggestArea) { biggestArea = area; biggestIdx = i; }
    });

    // Desenha cada rosto
    faces.forEach((f, i) => {
      const isBiggest = (i === biggestIdx);

      // Quadrado verde pro maior, amarelo pros outros
      _ctx.strokeStyle = isBiggest ? "#00ff00" : "#ffff00";
      _ctx.lineWidth   = isBiggest ? 3 : 2;
      _ctx.strokeRect(f.x, f.y, f.w, f.h);

      // Label com info
      const area  = Math.round(f.w * f.h);
      const label = `#${i + 1}  ${Math.round(f.w)}×${Math.round(f.h)}  area: ${area}`;
      const tag   = isBiggest ? " ★ SELECIONADO" : "";

      _ctx.fillStyle = isBiggest ? "#00ff00" : "#ffff00";
      _ctx.fillText(label + tag, f.x, f.y - 8);
    });

    // Info geral no canto
    _ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
    _ctx.fillRect(0, 0, 320, 30);
    _ctx.fillStyle = "#00ff00";
    _ctx.font = "bold 13px monospace";
    _ctx.fillText(`DEBUG | ${faces.length} rosto(s) | detector: ${detectorType}`, 8, 20);
  }

  // -----------------------------------------------------------------
  // Cálculo do crop
  // -----------------------------------------------------------------
  function computeCrop(face, vw, vh) {
    if (!face) return null;
    const { x, y, w, h } = face;

    const cx = x + w / 2;
    const cy = y + h / 2;
    const sz = Math.max(w, h);

    if (sz < C.minFaceSize) return null;

    let cw = sz * (1 + C.facePadding * 2);
    let ch = cw / C.aspectRatio;

    if (cw > vw) { cw = vw; ch = cw / C.aspectRatio; }
    if (ch > vh) { ch = vh; cw = ch * C.aspectRatio; }

    let ox = cx - cw / 2;
    let oy = (cy - sz * C.topBias) - ch / 2;

    const marginX = cw * C.marginSafety;
    const marginY = ch * C.marginSafety;

    const faceLeft   = x - ox;
    const faceRight  = (ox + cw) - (x + w);
    const faceTop    = y - oy;
    const faceBottom = (oy + ch) - (y + h);

    if (faceLeft   < marginX) ox -= (marginX - faceLeft);
    if (faceRight  < marginX) ox += (marginX - faceRight);
    if (faceTop    < marginY) oy -= (marginY - faceTop);
    if (faceBottom < marginY) oy += (marginY - faceBottom);

    ox = Math.max(0, Math.min(ox, vw - cw));
    oy = Math.max(0, Math.min(oy, vh - ch));

    return { x: ox, y: oy, w: cw, h: ch };
  }

  // -----------------------------------------------------------------
  // Suavização (lerp)
  // -----------------------------------------------------------------
  function smooth(target) {
    if (!crop) { crop = { ...target }; return crop; }
    const s = C.smoothing;
    crop.x = crop.x * s + target.x * (1 - s);
    crop.y = crop.y * s + target.y * (1 - s);
    crop.w = crop.w * s + target.w * (1 - s);
    crop.h = crop.h * s + target.h * (1 - s);
    return crop;
  }

  // -----------------------------------------------------------------
  // Loop de detecção
  // -----------------------------------------------------------------
  function startDetectLoop(v) {
    async function tick() {
      if (!running) return;
      const face = await detectFace(v);
      if (face) {
        const r = computeCrop(face, v.videoWidth, v.videoHeight);
        if (r) { lastDet = r; if (_onStatus) _onStatus("found"); }
      } else {
        if (_onStatus) _onStatus(lastDet ? "lost" : "searching");
      }
      if (running) detectTimer = setTimeout(tick, C.detectionInterval);
    }
    tick();
  }

  // -----------------------------------------------------------------
  // Loop de renderização
  // -----------------------------------------------------------------
  function startRenderLoop(v) {
    const outW = C.outputWidth;
    const outH = Math.round(outW / C.aspectRatio);

    function frame() {
      if (!running) return;
      if (v.readyState >= 2) {

        // ── Modo debug: mostra vídeo inteiro + quadrados ──
        if (C.debug) {
          drawDebugOverlay(v, lastFaces);
          animId = requestAnimationFrame(frame);
          return;
        }

        // ── Modo normal: crop com zoom suave ──
        _canvas.width  = outW;
        _canvas.height = outH;

        if (lastDet) {
          const c = smooth(lastDet);
          _ctx.drawImage(v, c.x, c.y, c.w, c.h, 0, 0, outW, outH);
        } else {
          // Sem detecção: crop central 1:1
          const vw = v.videoWidth, vh = v.videoHeight;
          const side = Math.min(vw, vh);
          _ctx.drawImage(v, (vw - side) / 2, (vh - side) / 2, side, side, 0, 0, outW, outH);
        }
      }
      animId = requestAnimationFrame(frame);
    }
    frame();
  }

  // -----------------------------------------------------------------
  // API pública
  // -----------------------------------------------------------------
  async function start(video, canvas, statusCb) {
    if (running) stop();
    _video    = video;
    _canvas   = canvas;
    _ctx      = canvas.getContext("2d");
    _onStatus = statusCb || null;

    const ok = await initDetector();
    if (!ok) { warn("Nenhum detector. Desabilitado."); return false; }

    running  = true;
    crop     = null;
    lastDet  = null;
    lastFaces = [];
    startDetectLoop(video);
    startRenderLoop(video);
    log("Iniciado ✔", C.debug ? "(modo DEBUG)" : "");
    return true;
  }

  function stop() {
    running = false;
    if (animId) cancelAnimationFrame(animId);
    if (detectTimer) clearTimeout(detectTimer);
    animId = null; detectTimer = null;
    crop = null; lastDet = null; lastFaces = [];
    log("Parado.");
  }

  function capture() {
    if (!_canvas) return null;
    return _canvas.toDataURL("image/jpeg", 0.90);
  }

  function isActive() { return running; }

  window.FaceCropper = { start, stop, capture, isActive, CONFIG: C };

})();
