// =====================================================================
// camera.js — SISPORT V2
// Câmera abre automaticamente. Preview no mesmo elemento.
// Borda verde ao capturar. Fluxo simplificado.
// =====================================================================

(function () {

  function log(...args) { console.log("[camera]", ...args); }

  // ── Listagem e filtro de câmeras ──────────────────────────────────

  async function listVideoInputs() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(d => d.kind === "videoinput");
  }

  function isProbablyVirtualCamera(label = "") {
    const s = label.toLowerCase();
    return ["obs","virtual","nvidia","broadcast","manycam","droidcam"]
      .some(k => s.includes(k));
  }

  // ── Abrir câmera ─────────────────────────────────────────────────

  async function openCamera(videoEl) {
    if (!videoEl) throw new Error("Elemento <video> não encontrado.");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    } catch (err1) {
      log("Tentativa 1 falhou:", err1?.name, err1?.message);

      const cams = await listVideoInputs();
      log("Dispositivos:", cams.map(c => ({ label: c.label, id: c.deviceId })));

      const preferred = cams.find(c => c.label && !isProbablyVirtualCamera(c.label)) || cams[0];
      if (!preferred) throw err1;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: { exact: preferred.deviceId },
          width: { ideal: 640 }, height: { ideal: 480 }
        },
        audio: false
      });
      videoEl.srcObject = stream;
      await videoEl.play();
      return stream;
    }
  }

  function stopCamera(stream) {
    if (stream) stream.getTracks().forEach(t => t.stop());
  }

  // ── Capturar frame do vídeo para o canvas ─────────────────────────

  function captureToCanvas(videoEl, canvasEl) {
    const w = videoEl.videoWidth || 640;
    const h = videoEl.videoHeight || 480;
    canvasEl.width = w;
    canvasEl.height = h;
    const ctx = canvasEl.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, w, h);
    return canvasEl.toDataURL("image/jpeg", 0.85);
  }

  // ── Helpers de visibilidade (vence Bootstrap d-flex) ──────────────

  function hide(el) {
    if (!el) return;
    el.classList.add("d-none");
    el.classList.remove("d-flex");
  }

  function showFlex(el) {
    if (!el) return;
    el.classList.add("d-flex");
    el.classList.remove("d-none");
  }

  // ── Validação global de foto obrigatória ──────────────────────────

  window.ensurePhoto = function ensurePhoto(e) {
    const submitter = e && e.submitter;
    if (submitter && submitter.name === "skip") return true;

    const input = document.getElementById("photo_data_url");
    if (!input || !input.value) {
      alert('Capture a foto antes de continuar.\nOu clique em "Pular sem foto".');
      return false;
    }
    return true;
  };

  // ── Inicialização principal (wizard etapa 2) ──────────────────────

  document.addEventListener("DOMContentLoaded", () => {

    const block = document.querySelector('[data-camera="1"]');
    if (!block) return;

    // Se o bloco está escondido (editor), não faz nada agora
    if (block.offsetParent === null) {
      log("Bloco de câmera oculto — aguardando sisport:open-camera.");
      return;
    }

    initCamera();
  });

  // ── Função central de inicialização ───────────────────────────────

  function initCamera() {
    const video        = document.getElementById("cam-video");
    const canvas       = document.getElementById("cam-canvas");
    const container    = document.getElementById("camera-container");
    const loading      = document.getElementById("cam-loading");
    const errorOverlay = document.getElementById("cam-error");
    const hiddenInput  = document.getElementById("photo_data_url");

    const btnCapture   = document.getElementById("btn-capture");
    const btnRetake    = document.getElementById("btn-retake");
    const btnNext      = document.getElementById("btn-next");
    const btnSkip      = document.getElementById("skip-btn");

    if (!video || !container) return;

    let stream = null;

    // ── Estados visuais ─────────────────────────────────────────────

    function setStateLive() {
      video.style.display = "block";
      canvas.style.display = "none";
      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      container.style.borderWidth = "";

      if (btnCapture) { btnCapture.style.display = "block"; btnCapture.disabled = false; }
      if (btnRetake)    btnRetake.style.display = "none";
      if (btnNext)      btnNext.disabled = true;
      if (hiddenInput)  hiddenInput.value = "";
    }

    function setStateCaptured(dataUrl) {
      video.style.display = "none";
      canvas.style.display = "block";
      container.classList.remove("border-secondary");
      container.classList.add("border-success");
      container.style.borderWidth = "3px";

      if (btnCapture) btnCapture.style.display = "none";
      if (btnRetake)  btnRetake.style.display = "block";
      if (btnNext)    btnNext.disabled = false;
      if (hiddenInput) hiddenInput.value = dataUrl;
    }

    function setStateError() {
      hide(loading);
      showFlex(errorOverlay);
      if (btnCapture) btnCapture.disabled = true;
    }

    function setStateReady() {
      hide(loading);
      hide(errorOverlay);
      setStateLive();
    }

    // ── Abrir câmera ────────────────────────────────────────────────

    async function startCamera() {
      // Mostra loading, esconde erro
      showFlex(loading);
      hide(errorOverlay);

      try {
        stream = await openCamera(video);
        log("Câmera aberta com sucesso.");
        setStateReady();
      } catch (err) {
        console.error("[camera] Falha ao abrir:", err?.name, err?.message, err);
        setStateError();
      }
    }

    // ── Auto-abrir ──────────────────────────────────────────────────
    startCamera();

    // ── Botão TIRAR FOTO ────────────────────────────────────────────

    btnCapture?.addEventListener("click", () => {
      if (!stream || !video) return;
      const dataUrl = captureToCanvas(video, canvas);
      setStateCaptured(dataUrl);
      log("Foto capturada.");
    });

    // ── Botão TIRAR OUTRA ───────────────────────────────────────────

    btnRetake?.addEventListener("click", () => {
      setStateLive();
      if (!stream || !video.srcObject) {
        startCamera();
      }
      log("Modo retake — câmera ao vivo.");
    });

    // ── Botão PULAR ─────────────────────────────────────────────────

    btnSkip?.addEventListener("click", () => {
      if (hiddenInput) hiddenInput.value = "";
    });

    // ── Cleanup ─────────────────────────────────────────────────────

    window.addEventListener("beforeunload", () => stopCamera(stream));
  }

  // ── Abertura sob demanda (tela de edição) ───────────────────────

  window.addEventListener("sisport:open-camera", () => {
    const video = document.getElementById("cam-video");
    if (!video) return;

    // Se já tem stream rodando, não reabre
    if (video.srcObject) {
      log("Câmera já ativa, ignorando.");
      const loading = document.getElementById("cam-loading");
      hide(loading);
      return;
    }

    initCamera();
  });

})();
